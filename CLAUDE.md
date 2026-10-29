# GNTC Research Dashboard

Streamlit 市場研究／公司分析／競品監測工具。引擎：GPT Researcher 0.16.1 + Google Gemini（免費版）+ Tavily。

## 環境與指令（Windows PowerShell，Python 3.12）
- 啟動：`.\.venv\Scripts\python.exe -m streamlit run app.py`
- 測試：`.\.venv\Scripts\python.exe -m unittest -v test_dashboard`
- 每次修改後都要跑完整測試，全部通過才算完成。
- 不要執行 `smoke_research.py` 或 `monitor_cli.py`，除非使用者明確要求：它們會用掉真實的 Gemini／Tavily 額度。

## 檔案分工
- `research_agent.py`：研究流程、提示詞（REPORT_PROMPT／COMPANY_PROMPT）、金鑰處理、錯誤訊息、額度偵測（QuotaGuard）
- `evidence.py`：來源日期推測、摘錄、〔待驗證〕標記（規則判斷，不是 AI）
- `registry.py`：經濟部商工登記開放資料 API（免金鑰）
- `history.py`：SQLite 研究歷史（`data/research_history.db`）；寫入後呼叫 `on_write`
- `cloud_store.py`：設定 `SUPABASE_URL`／`SUPABASE_SERVICE_KEY` 時，啟動時從 Supabase Storage 還原資料庫檔、每次寫入後上傳；還原失敗就不上傳
- `monitor.py`／`monitor_cli.py`：競品監測與 Windows 排程入口
- `app.py`：Streamlit 介面

## 必須遵守的規則
- **語言**：所有 UI 文字、報告、錯誤訊息一律用臺灣繁體中文（臺灣用語，例如「資料」「網址」「金鑰」「伺服器」，不用「數據庫」「鏈接」「密鑰」「服務器」）。
- **不洩漏金鑰**：絕不把例外原文顯示給使用者或寫入資料庫，一律用 `research_agent.error_message(exc)`；要記錄 traceback 時用 `log_failure()`（會遮蔽金鑰）。
- **測試不打真實 API**：GPTResearcher、Gemini、Tavily、經濟部 API、Supabase 一律 mock（參考 `FakeRegistryClient`、`FakeStorage` 與 `ResearchTests.fake`）。
- **測試不碰真實資料庫**：用 `TempHistoryMixin`，不要寫入 `data/`。
- **資料庫升級**：新增欄位時，在 `_connect()` 用 `ALTER TABLE ... ADD COLUMN` 升級舊資料庫，並加一個舊資料庫升級的測試。不可刪除或改名既有欄位。
- **官方資料不經 AI 改寫**：`registry.to_markdown()` 的內容在 `mark_unverified` 之後才加入報告，不可讓模型改寫。
- **共用環境變數**：金鑰透過 `use_api_keys()` 暫時套用並加鎖；不要直接改 `os.environ` 的金鑰。
- **GPT Researcher 版本固定 0.16.1**：`_patch_llm_text_output()` 依賴其內部 API，升級前必須確認相容。

## 風格
- 保持現有寫法：函式短小、單引號、行寬約 120。
- 修改 Streamlit 元件時，保留既有的 `key=`，測試依賴它們。
- 不要新增套件，除非必要；新增時更新 `requirements.txt` 並固定版本。
- `.env` 永遠不可加入 Git 或貼到對話中。
