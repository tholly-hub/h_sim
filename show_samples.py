"""サンプルデータ表示確認スクリプト"""
import sqlite3

conn = sqlite3.connect("data/horse_racing_sim.db")
conn.row_factory = sqlite3.Row

print("=== 馬主サンプル (10件) ===")
for r in conn.execute("SELECT * FROM owners LIMIT 10"):
    print(f"ID:{r['owner_id']:<2} 馬主名: {r['name']:<16} | 冠名: 【{r['prefix']}】 | 資金: {r['funds']:,}円")

print("\n=== 現役競走馬サンプル (10件) ===")
for r in conn.execute(
    """
    SELECT h.horse_id, h.name, h.sex, h.age, h.mstn_type, h.speed, h.stamina, 
           o.name as owner_name, o.prefix, b.name as breeder_name,
           t.name as trainer_name, t.location as trainer_loc,
           j.name as jockey_name
    FROM horses h
    JOIN owners o ON h.owner_id = o.owner_id
    JOIN breeders b ON h.breeder_id = b.breeder_id
    LEFT JOIN trainers t ON h.trainer_id = t.trainer_id
    LEFT JOIN jockeys j ON h.jockey_id = j.jockey_id
    WHERE h.is_active = 1
    LIMIT 10
    """
):
    print(f"ID:{r['horse_id']:<4} 馬名: 【{r['name']:<12}】 ({r['sex']}, {r['age']}歳) | 厩舎: {r['trainer_name']} [{r['trainer_loc']}] | 主戦: {r['jockey_name']} | 牧場: {r['breeder_name']}")

print("\n=== 厩舎サンプル (5件: 美浦・栗東) ===")
for r in conn.execute(
    """
    SELECT t.trainer_id, t.name, t.location, t.specialty, t.horse_capacity,
           COUNT(h.horse_id) as horse_count
    FROM trainers t
    LEFT JOIN horses h ON t.trainer_id = h.trainer_id AND h.is_active = 1
    GROUP BY t.trainer_id
    LIMIT 5
    """
):
    print(f"ID:{r['trainer_id']:<2} 厩舎: {r['name']:<10} | 所属: {r['location']} | 特徴: {r['specialty']:<12} | 管理頭数: {r['horse_count']}/{r['horse_capacity']}頭")

print("\n=== 騎手サンプル (5件) ===")
for r in conn.execute(
    """
    SELECT jockey_id, name, location, age, career_years,
           (skill + drive + start_dash + temperament_handling)/4.0 as total_ability,
           career_wins, career_rides
    FROM jockeys
    WHERE is_active = 1
    LIMIT 5
    """
):
    print(f"ID:{r['jockey_id']:<2} 騎手: {r['name']:<10} | 所属: {r['location']} | 年齢: {r['age']}歳 ({r['career_years']}年目) | 総合能力: {r['total_ability']:.1f} | 通算: {r['career_wins']}/{r['career_rides']}回")

print("\n=== 種牡馬サンプル (5件) ===")
for r in conn.execute(
    """
    SELECT s.sire_id, h.name, h.age, s.sire_line, s.stud_fee, o.name as owner_name, o.prefix, b.name as breeder_name
    FROM sires s
    JOIN horses h ON s.horse_id = h.horse_id
    JOIN owners o ON h.owner_id = o.owner_id
    JOIN breeders b ON s.breeder_id = b.breeder_id
    LIMIT 5
    """
):
    print(f"ID:{r['sire_id']:<2} 馬名: 【{r['name']:<12}】 ({r['age']}歳) | 系統: {r['sire_line']:<18} | 繋養: {r['breeder_name']}")
