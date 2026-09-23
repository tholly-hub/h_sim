# エラー原因調査 & 修正完了ウォークスルー

## 1. 発生していたエラーの原因

ご提示いただいた macOS クラッシュレポート（`EXC_CRASH (SIGABRT)` / `Abort trap: 6` / `QMessageLogger::fatal` / `pyqt6_err_print()`）を解析し、以下の原因を特定・解消しました。

### ① `matings` テーブル定義の不足による SQLite エラー
- **原因**: 
  - データベース初期化時に `matings` テーブルがスキーマ定義（`src/db/schema.py`）に含まれておらず、初回進行時やダイアログ読み込み時に `sqlite3.OperationalError: no such table: matings` が発生していました。
- **対応**: 
  - `src/db/schema.py` に `matings`（交配・受胎記録テーブル）および各インデックス定義を追加しました。
  - `SpringBreedingDialog` 内でもテーブル存在を事前保証するよう安全対策を追加しました。

### ② ダッシュボード「次の週に進む」時の変数未定義 & 二重実行
- **原因**: 
  - `src/gui/views/dashboard_view.py` の `_advance_to_next_week` メソッド内の分岐で `next_y` / `next_w` 変数が未定義のまま `cal.run_week` が呼ばれる箇所があり、`UnboundLocalError` が発生していました。
  - また、`run_week` の前後に `perform_spring_foaling` / `perform_spring_mating` が重複して呼ばれる状態になっていました。
- **対応**: 
  - `next_y` / `next_w` を正しく設定し、`run_week` 内での正規実行後にダイアログ（3月出産、4月種付け、10月未勝利引退）をポップアップ表示するフローに整理しました。

### ③ PyQt6 の例外によるプロセス強制終了（SIGABRT）の防止
- **原因**: 
  - PyQt6 では、ボタンクリック等の Qt スロット内で未捕捉例外が発生すると、デフォルトで `qFatal()` が呼ばれ、プロセスがクラッシュ（`SIGABRT`）する仕様になっていました。
- **対応**: 
  - `src/gui/app.py` にグローバル例外ハンドラ（`sys.excepthook = _global_exception_hook`）を設定し、万一の例外発生時にもクラッシュさせず、詳細なログと警告ダイアログを表示して安全に継続できるようにしました。

---

## 2. 検証結果

- **GUI 進行・統合テスト (`tests/test_gui_advance_crash.py`)**:
  - メインウィンドウ起動、ダッシュボードでの週進行（第21週→第22週）、3月出産ダイアログ・4月種付けダイアログの表示、全5タブ切り替えが例外なくすべて正常に完了することを確認しました。
- **全ユニットテストスイート (`python3 -m unittest discover -s tests`)**:
  - 116件すべてのテストが **OK (Passed)** となることを確認しました。
