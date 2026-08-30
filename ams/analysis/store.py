# -*- coding: utf-8 -*-
"""
store.py — SQLite + JSONL 持久化（升级自 data_store.py）

- candidates 表：每条攻击候选全生命周期字段
- generations 表：每代汇总
- experiments 表：实验元信息
- 查询接口：按检测器/语言/策略/场景 统计；导出训练数据（"攻击即数据"回流管道）
"""
import json
import os
import sqlite3
from datetime import datetime

CANDIDATE_COLS = """id TEXT PRIMARY KEY, experiment_id TEXT, scenario_kind TEXT,
    scenario_id TEXT, generation INTEGER, island INTEGER,
    prompt TEXT, trigger TEXT, improvement TEXT, attack_type TEXT,
    harm_category TEXT, defense_applied TEXT, language TEXT,
    detector_id TEXT, det_score REAL, det_blocked INTEGER, det_label TEXT, det_model TEXT,
    victim_response TEXT, agent_trace TEXT, judge_verdict TEXT, judge_jailbreak INTEGER,
    goal_achieved INTEGER, success INTEGER,
    critic_score REAL, critic_advice TEXT, fitness REAL,
    llm_calls INTEGER, detector_calls INTEGER, cost_usd REAL,
    queries_so_far INTEGER, created_at TEXT, evaluated_at TEXT"""


class DataStore:
    def __init__(self, output_dir="./redteam_output"):
        self.dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "exports"), exist_ok=True)
        self.db = os.path.join(output_dir, "redteam.db")
        self.jsonl = os.path.join(output_dir, "candidates.jsonl")
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        conn = self._conn()
        conn.execute(f"CREATE TABLE IF NOT EXISTS candidates ({CANDIDATE_COLS})")
        conn.execute("""CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT,
            generation INTEGER, scenario_kind TEXT, scenario_id TEXT, detector_id TEXT,
            n_candidates INTEGER, n_success INTEGER, n_jailbroken INTEGER,
            n_bypassed INTEGER, n_blocked INTEGER,
            avg_fitness REAL, avg_det_score REAL, elapsed_seconds REAL,
            languages_tested TEXT, timestamp TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY, config TEXT, created_at TEXT,
            summary TEXT)""")
        conn.commit()
        conn.close()

    # ---------- 写入 ----------
    def insert_candidate(self, cand, exp_id=""):
        d = cand.to_dict()
        d["experiment_id"] = exp_id or cand.experiment_id
        for k in ("det_blocked", "judge_jailbreak", "goal_achieved", "success"):
            d[k] = int(bool(d.get(k, False)))
        d["agent_trace"] = json.dumps(
            [repr(t) for t in d.get("agent_trace", [])], ensure_ascii=False)
        keep = {k: d.get(k) for k in
                [r.split()[0] for r in CANDIDATE_COLS.split(",")]}
        conn = self._conn()
        try:
            cols = ",".join(keep.keys())
            ph = ",".join(["?"] * len(keep))
            conn.execute(f"INSERT OR REPLACE INTO candidates ({cols}) "
                         f"VALUES ({ph})", list(keep.values()))
            conn.commit()
        except Exception as e:
            print(f"  SQL err: {e}")
        finally:
            conn.close()
        with open(self.jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")

    def insert_generation(self, rec, exp_id=""):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO generations VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (exp_id, rec.generation, rec.scenario_kind, rec.scenario_id,
                 rec.detector_id, rec.n_candidates, rec.n_success, rec.n_jailbroken,
                 rec.n_bypassed, rec.n_blocked, rec.avg_fitness, rec.avg_det_score,
                 rec.elapsed_seconds, ",".join(rec.languages_tested), rec.timestamp))
            conn.commit()
        except Exception as e:
            print(f"  SQL gen err: {e}")
        finally:
            conn.close()

    def upsert_experiment(self, exp_id, config=None, summary=None):
        conn = self._conn()
        conn.execute("""INSERT INTO experiments (experiment_id, config, created_at, summary)
            VALUES (?,?,?,?)
            ON CONFLICT(experiment_id) DO UPDATE SET summary=excluded.summary""",
            (exp_id, json.dumps(config or {}, ensure_ascii=False, default=str),
             datetime.now().isoformat(),
             json.dumps(summary or {}, ensure_ascii=False, default=str)))
        conn.commit()
        conn.close()

    # ---------- 查询 ----------
    def query(self, where="1=1", params=()):
        conn = self._conn()
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM candidates WHERE {where} ORDER BY fitness DESC", params)]
        conn.close()
        for r in rows:
            r["det_blocked"] = bool(r["det_blocked"])
            r["judge_jailbreak"] = bool(r["judge_jailbreak"])
            r["goal_achieved"] = bool(r["goal_achieved"])
            r["success"] = bool(r["success"])
        return rows

    def query_success(self, exp_id=None):
        w, p = "success=1", ()
        if exp_id:
            w += " AND experiment_id=?"
            p = (exp_id,)
        return self.query(w, p)

    def stats_by(self, column, exp_id=None):
        conn = self._conn()
        w, p = "1=1", ()
        if exp_id:
            w = "experiment_id=?"
            p = (exp_id,)
        rows = [dict(r) for r in conn.execute(f"""
            SELECT {column} AS k, COUNT(*) AS total,
              SUM(success) AS success,
              SUM(judge_jailbreak OR goal_achieved) AS attack_ok,
              SUM(CASE WHEN det_blocked=0 AND (judge_jailbreak=1 OR goal_achieved=1) THEN 1 ELSE 0 END) AS bypassed,
              AVG(det_score) AS avg_det
            FROM candidates WHERE {w} GROUP BY {column} ORDER BY bypassed DESC""", p)]
        conn.close()
        return rows

    # ---------- 训练数据回流 ----------
    def export_training_data(self, exp_id=None):
        """论文启示 5.2：在预收集固定样本上训练不泛化 → 维护"攻击即数据"回流管道。
        正例 = 绕过检测器且攻击成功的样本（检测器的漏报）；
        负例 = 被拦截的攻击样本（检测器已抓住，用于防误报校准）+ 良性负样本。"""
        w, p = "1=1", ()
        if exp_id:
            w = "experiment_id=?"
            p = (exp_id,)
        conn = self._conn()
        pos = [dict(r) for r in conn.execute(
            f"SELECT * FROM candidates WHERE {w} AND success=1", p)]
        blocked = [dict(r) for r in conn.execute(
            f"SELECT * FROM candidates WHERE {w} AND det_blocked=1", p)]
        benign = [dict(r) for r in conn.execute(
            f"SELECT * FROM candidates WHERE {w} AND det_blocked=1 "
            f"AND (judge_jailbreak=0 AND goal_achieved=0)", p)]
        conn.close()
        path = os.path.join(self.dir, "exports",
                            f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        n = 0
        with open(path, "w", encoding="utf-8") as f:
            for r in pos:
                f.write(json.dumps({
                    "text": r["prompt"], "label": r.get("harm_category", "attack"),
                    "should_block": True, "source": "ams_bypassed",
                    "attack_type": r["attack_type"], "language": r["language"],
                    "scenario_kind": r["scenario_kind"],
                    "detector_missed": r["detector_id"],
                    "det_score_was": r["det_score"]}, ensure_ascii=False) + "\n")
                n += 1
            for r in blocked:
                f.write(json.dumps({
                    "text": r["prompt"], "label": "attack_caught",
                    "should_block": True, "source": "ams_blocked",
                    "attack_type": r["attack_type"], "language": r["language"]},
                    ensure_ascii=False) + "\n")
                n += 1
            for r in benign:
                f.write(json.dumps({
                    "text": r["prompt"], "label": "normal",
                    "should_block": False, "source": "ams_negative"},
                    ensure_ascii=False) + "\n")
                n += 1
        print(f"  Training data: {path} ({len(pos)} missed-attacks + "
              f"{len(blocked)} caught + {len(benign)} benign = {n})")
        return path
