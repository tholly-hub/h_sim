"""
5代血統表 インタラクティブHTML生成モジュール
- 父系・母系を階層化したnetkeiba風の5代血統表グリッド
- 表中の各馬をクリックすると成績・能力値・主な勝ち鞍をモーダル表示
- クリックした祖先馬の血統表へ動的に遷移可能
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.db.database import Database


class PedigreeBuilder:
    """5代血統表 HTML生成クラス"""

    def __init__(self, db: Database):
        self.db = db

    def get_ancestors_tree(self, horse_id: int, depth: int = 5) -> Dict[str, Any]:
        """指定馬を起点として5代前までの祖先ツリー（最大62頭）を再帰的に取得"""
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT h.*, 
                       o.name as owner_name, 
                       b.name as breeder_name, 
                       t.name as trainer_name,
                       j.name as jockey_name
                FROM horses h
                LEFT JOIN owners o ON h.owner_id = o.owner_id
                LEFT JOIN breeders b ON h.breeder_id = b.breeder_id
                LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
                LEFT JOIN jockeys j ON h.jockey_id = j.jockey_id
                WHERE h.horse_id = ?
                """,
                (horse_id,),
            ).fetchone()

            if not row:
                return {
                    "horse_id": horse_id,
                    "name": "不明 (始祖馬)",
                    "sex": "horse",
                    "birth_year": 0,
                    "age": 0,
                    "starts": 0,
                    "wins": 0,
                    "g1_wins": 0,
                    "g2_wins": 0,
                    "g3_wins": 0,
                    "prize_money": 0,
                    "major_wins": "-",
                    "speed": 50.0,
                    "stamina": 50.0,
                    "acceleration": 50.0,
                    "growth_type": "normal",
                    "running_style": "between",
                    "sire": None,
                    "dam": None,
                }

            node = {
                "horse_id": row["horse_id"],
                "name": row["name"],
                "sex": row["sex"],
                "birth_year": row["birth_year"],
                "age": row["age"],
                "owner_name": row["owner_name"] or "未定",
                "breeder_name": row["breeder_name"] or "未定",
                "trainer_name": row["trainer_name"] or "未入厩",
                "jockey_name": row["jockey_name"] or "主戦未定",
                "starts": row["career_starts"],
                "wins": row["career_wins"],
                "g1_wins": row["g1_wins"],
                "g2_wins": row["g2_wins"] if "g2_wins" in row.keys() else 0,
                "g3_wins": row["g3_wins"] if "g3_wins" in row.keys() else 0,
                "prize_money": row["prize_money"],
                "major_wins": row["major_wins"] or "なし",
                "speed": round(row["speed"], 1),
                "stamina": round(row["stamina"], 1),
                "acceleration": round(row["acceleration"], 1),
                "growth_type": row["growth_type"],
                "running_style": row["running_style"],
                "sire": None,
                "dam": None,
            }

            if depth > 1:
                if row["sire_id"]:
                    node["sire"] = self.get_ancestors_tree(row["sire_id"], depth - 1)
                if row["dam_id"]:
                    node["dam"] = self.get_ancestors_tree(row["dam_id"], depth - 1)

            return node

    def build_html(self, horse_id: int, output_path: Optional[str] = None) -> str:
        """5代血統表のインタラクティブHTMLを生成してファイルに保存"""
        tree_data = self.get_ancestors_tree(horse_id, depth=5)
        tree_json = json.dumps(tree_data, ensure_ascii=False)

        html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>【5代血統表】{tree_data['name']}</title>
    <style>
        :root {{
            --bg-main: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --sire-bg: #1e3a8a;
            --sire-hover: #2563eb;
            --dam-bg: #831843;
            --dam-hover: #db2777;
            --accent: #f59e0b;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-main);
            color: var(--text-main);
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        header {{
            width: 100%;
            max-width: 1400px;
            margin-bottom: 20px;
            padding: 20px;
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-title h1 {{
            font-size: 26px;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .header-title .tag {{
            font-size: 14px;
            padding: 4px 10px;
            border-radius: 6px;
            background: var(--accent);
            color: #000;
            font-weight: 600;
        }}
        .header-info {{
            font-size: 15px;
            color: var(--text-muted);
            margin-top: 6px;
        }}
        .grid-container {{
            width: 100%;
            max-width: 1400px;
            overflow-x: auto;
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 16px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
        }}
        table.pedigree-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}
        th, td {{
            border: 1px solid var(--border-color);
            padding: 6px 8px;
            text-align: left;
            vertical-align: middle;
        }}
        th {{
            background: #0f172a;
            color: var(--text-muted);
            font-size: 12px;
            text-align: center;
            padding: 10px;
        }}
        .horse-cell {{
            cursor: pointer;
            transition: all 0.2s ease;
            border-radius: 4px;
            padding: 8px 10px;
            font-size: 13px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .horse-cell.sire {{
            background: rgba(30, 58, 138, 0.4);
            border-left: 4px solid #3b82f6;
        }}
        .horse-cell.sire:hover {{
            background: rgba(37, 99, 235, 0.6);
            transform: translateY(-1px);
        }}
        .horse-cell.dam {{
            background: rgba(131, 24, 67, 0.4);
            border-left: 4px solid #ec4899;
        }}
        .horse-cell.dam:hover {{
            background: rgba(219, 39, 119, 0.6);
            transform: translateY(-1px);
        }}
        .horse-cell .cell-name {{
            font-weight: bold;
            color: #ffffff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .horse-cell .cell-sub {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        /* モーダル */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(4px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .modal-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            width: 90%;
            max-width: 580px;
            padding: 28px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8);
            position: relative;
            animation: fadeIn 0.2s ease-out;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: scale(0.95); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}
        .modal-close {{
            position: absolute;
            top: 18px; right: 20px;
            background: none; border: none;
            font-size: 24px; color: var(--text-muted);
            cursor: pointer;
        }}
        .modal-close:hover {{ color: #ffffff; }}
        .modal-header {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 14px;
            margin-bottom: 18px;
        }}
        .modal-header h2 {{
            font-size: 24px;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 18px;
        }}
        .stat-box {{
            background: #0f172a;
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        .stat-label {{
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 2px;
        }}
        .stat-value {{
            font-size: 15px;
            font-weight: 600;
            color: #f1f5f9;
        }}
        .major-wins-box {{
            background: #0f172a;
            padding: 12px 14px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            margin-bottom: 18px;
        }}
        .modal-actions {{
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 10px;
        }}
        .btn {{
            padding: 9px 18px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }}
        .btn-primary {{
            background: #3b82f6;
            color: #ffffff;
        }}
        .btn-primary:hover {{ background: #2563eb; }}
    </style>
</head>
<body>
    <header>
        <div class="header-title">
            <h1 id="rootNameHeader">
                <span id="rootHorseName">{tree_data['name']}</span>
                <span class="tag" id="rootHorseSex">{tree_data['sex']}</span>
            </h1>
            <div class="header-info" id="rootHorseInfo">
                馬ID: {tree_data['horse_id']} | 生年: {tree_data['birth_year']}年 | 所属: {tree_data.get('trainer_name', '未定')} | 主戦: {tree_data.get('jockey_name', '未定')}
            </div>
        </div>
        <div>
            <span style="font-size: 12px; color: var(--text-muted);">※表中の馬名をクリックすると詳細成績が表示されます</span>
        </div>
    </header>

    <div class="grid-container">
        <table class="pedigree-table" id="pedigreeTable">
            <thead>
                <tr>
                    <th style="width: 20%;">父 / 母 (1代前)</th>
                    <th style="width: 20%;">祖父母 (2代前)</th>
                    <th style="width: 20%;">曾祖父母 (3代前)</th>
                    <th style="width: 20%;">4代前</th>
                    <th style="width: 20%;">5代前</th>
                </tr>
            </thead>
            <tbody id="pedigreeBody">
                <!-- JavaScriptで32行×5列を動的構築 -->
            </tbody>
        </table>
    </div>

    <!-- 詳細モーダル -->
    <div class="modal-overlay" id="horseModal">
        <div class="modal-card">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <div class="modal-header">
                <h2>
                    <span id="modalHorseName">-</span>
                    <span class="tag" id="modalHorseSex" style="font-size: 12px;">-</span>
                </h2>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;" id="modalHorseMeta">-</div>
            </div>
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-label">生涯戦績</div>
                    <div class="stat-value" id="modalRecord">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">総獲得賞金</div>
                    <div class="stat-value" id="modalEarnings">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">重賞勝利数</div>
                    <div class="stat-value" id="modalGradedWins">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">能力評価 (速度 / 持久)</div>
                    <div class="stat-value" id="modalAbilities">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">脚質・成長型</div>
                    <div class="stat-value" id="modalStyleGrowth">-</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">生産牧場 / 馬主</div>
                    <div class="stat-value" id="modalBreederOwner" style="font-size: 13px;">-</div>
                </div>
            </div>
            <div class="major-wins-box">
                <div class="stat-label">主な勝ち鞍</div>
                <div class="stat-value" id="modalMajorWins" style="color: var(--accent);">-</div>
            </div>
            <div class="modal-actions">
                <button class="btn btn-primary" id="btnSwitchRoot">この馬の5代血統表を開く</button>
            </div>
        </div>
    </div>

    <script>
        const initialTreeData = {tree_json};
        let currentRoot = initialTreeData;
        let selectedHorse = null;

        // 5代（深さ5）の各スロット（32葉）のパス定義
        // 各スロット 0..31 に対し、深さ1〜5の親を特定
        function renderTable(root) {{
            const tbody = document.getElementById("pedigreeBody");
            tbody.innerHTML = "";

            // 32行を生成
            for (let r = 0; r < 32; r++) {{
                const tr = document.createElement("tr");

                // 各代 (col 0: 1代前, col 1: 2代前, col 2: 3代前, col 3: 4代前, col 4: 5代前)
                for (let c = 0; c < 5; c++) {{
                    const span = Math.pow(2, 4 - c); // col0: 16行結合, col1: 8行, col2: 4行, col3: 2行, col4: 1行
                    if (r % span === 0) {{
                        const td = document.createElement("td");
                        td.rowSpan = span;

                        // r と c から該当するノードをツリーから探索
                        const node = getNodeByRowCol(root, r, c);
                        const isSire = (Math.floor(r / (span / 2)) % 2 === 0);
                        const roleClass = isSire ? "sire" : "dam";

                        if (node) {{
                            td.innerHTML = `
                                <div class="horse-cell ${{roleClass}}" onclick="openModal(${{JSON.stringify(node).replace(/"/g, '&quot;')}})">
                                    <div class="cell-name">${{node.name}}</div>
                                    <div class="cell-sub">${{node.sex === 'horse' || node.sex === 'colt' ? '牡' : '牝'}} | ${{node.wins || 0}}勝</div>
                                </div>
                            `;
                        }} else {{
                            td.innerHTML = `
                                <div class="horse-cell ${{roleClass}}" style="opacity: 0.5;">
                                    <div class="cell-name" style="color: #94a3b8;">不明 (始祖馬)</div>
                                </div>
                            `;
                        }}
                        tr.appendChild(td);
                    }}
                }}
                tbody.appendChild(tr);
            }}
        }}

        function getNodeByRowCol(root, row, col) {{
            // col 0: 1代前 (row < 16: sire, row >= 16: dam)
            let curr = root;
            for (let c = 0; c <= col; c++) {{
                if (!curr) return null;
                const span = Math.pow(2, 4 - c);
                const bit = Math.floor(row / span) % 2;
                if (c === col) {{
                    return bit === 0 ? curr.sire : curr.dam;
                }} else {{
                    curr = bit === 0 ? curr.sire : curr.dam;
                }}
            }}
            return curr;
        }}

        function openModal(horse) {{
            if (!horse || horse.name.includes("不明")) return;
            selectedHorse = horse;
            document.getElementById("modalHorseName").innerText = horse.name;
            document.getElementById("modalHorseSex").innerText = horse.sex === 'horse' || horse.sex === 'colt' ? '牡' : '牝';
            document.getElementById("modalHorseMeta").innerText = `馬ID: ${{horse.horse_id}} | 生年: ${{horse.birth_year}}年`;
            document.getElementById("modalRecord").innerText = `${{horse.starts || 0}}戦 ${{horse.wins || 0}}勝`;
            document.getElementById("modalEarnings").innerText = `${{(horse.prize_money || 0).toLocaleString()}} 円`;
            document.getElementById("modalGradedWins").innerText = `G1: ${{horse.g1_wins || 0}}勝 / G2: ${{horse.g2_wins || 0}}勝 / G3: ${{horse.g3_wins || 0}}勝`;
            document.getElementById("modalAbilities").innerText = `速: ${{horse.speed || '-'}} / 耐: ${{horse.stamina || '-'}} / 瞬: ${{horse.acceleration || '-'}}`;
            
            const styleMap = {{'escape':'逃げ', 'leading':'先行', 'between':'差し', 'closing':'追込'}};
            const growthMap = {{'early':'早熟', 'normal':'普通', 'late':'晩成'}};
            document.getElementById("modalStyleGrowth").innerText = `${{growthMap[horse.growth_type] || horse.growth_type || '-'}} / ${{styleMap[horse.running_style] || horse.running_style || '-'}}`;
            document.getElementById("modalBreederOwner").innerText = `${{horse.breeder_name || '-'}} / ${{horse.owner_name || '-'}}`;
            document.getElementById("modalMajorWins").innerText = horse.major_wins || 'なし';

            document.getElementById("horseModal").style.display = "flex";
        }}

        function closeModal() {{
            document.getElementById("horseModal").style.display = "none";
        }}

        document.getElementById("btnSwitchRoot").onclick = function() {{
            if (selectedHorse) {{
                // 祖先馬を起点にして動的再描画
                currentRoot = selectedHorse;
                document.getElementById("rootHorseName").innerText = currentRoot.name;
                document.getElementById("rootHorseSex").innerText = currentRoot.sex === 'horse' || currentRoot.sex === 'colt' ? '牡' : '牝';
                document.getElementById("rootHorseInfo").innerText = `馬ID: ${{currentRoot.horse_id}} | 生年: ${{currentRoot.birth_year}}年 | 所属: ${{currentRoot.trainer_name || '未定'}}`;
                renderTable(currentRoot);
                closeModal();
            }}
        }};

        window.onclick = function(e) {{
            const modal = document.getElementById("horseModal");
            if (e.target === modal) {{
                closeModal();
            }}
        }};

        // 初期描画
        renderTable(initialTreeData);
    </script>
</body>
</html>
"""
        if output_path is None:
            output_dir = Path("data/reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"pedigree_{horse_id}.html")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_template)

        return output_path
