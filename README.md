# GNTC Streamlit AI Research Dashboard

第一階段可執行的市場研究 Dashboard。使用 GPT Researcher 搜尋 Tavily、以 Google Gemini 模型（免費版即可）整理資料，輸出繁體中文 Markdown 報告（摘要、市場趨勢、競品分析、風險、結論與引用）。含側邊選單、設定提示、階段進度與執行時間、Evidence Viewer、「〔待驗證〕」標示、SQLite 研究歷史及 Markdown 下載。沒有模擬報告模式。

## 啟動（Windows PowerShell，Python 3.12）

從目前工作區進入專案：

```powershell
cd 'C:\Users\mikelee\Desktop\GNTC Market Research\gntc-research'
# 若沒有虛擬環境，才執行：
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 僅第一次且沒有 .env 時複製；不要覆蓋自己的金鑰
Copy-Item .env.example .env
```

API Key 有兩種設定方式（`GOOGLE_API_KEY` 於 https://aistudio.google.com/apikey 免費取得，`TAVILY_API_KEY` 於 https://app.tavily.com/ 取得）：

- **在 Dashboard 左側欄直接填寫**：只在這次瀏覽中使用，不寫入任何檔案，重新整理頁面後需重填；按「儲存到 .env」則寫入專案 `.env`（保留其他設定），下次啟動自動載入。填寫的金鑰優先於 `.env` 與環境變數。
- **編輯 `.env`**：環境變數優先於 `.env`；更新後重新啟動。

GPT Researcher 從行程環境變數讀取金鑰，因此填寫的金鑰只在研究執行期間套用，結束後還原；多個瀏覽器同時使用同一台伺服器時，研究會依序執行，避免互相用到對方的金鑰。`monitor_cli.py` 與排程只讀取 `.env`。不要把 `.env` 加到 Git 或分享。介面的「✅」僅代表有值，不代表已驗證有效。

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

開啟 http://localhost:8501 。輸入主題、按「開始 AI 研究」，等待完成，再查看報告與來源或下載 Markdown。下載後報告保留於目前 Streamlit session；重新整理或關閉 session 可能清除結果。失敗的新研究會清除舊結果，避免誤認。

若目前的既有虛擬環境沒有 pip，可使用已安裝的 uv：

```powershell
uv --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe -r requirements.txt
```

## 設定與實作

- `app.py`：Streamlit Dashboard，Market Research / 研究歷史 / API 設定。報告頁含「研究報告」與「Evidence Viewer」分頁，以及蒐集來源、報告引用來源、待驗證項目、執行時間、估計費用指標。
- `research_agent.py`：載入專案目錄的 .env、驗證、async 研究流程、來源去重、錯誤提示；把 Gemini 回傳的內容區塊轉成純文字（GPT Researcher 0.16.1 只接受字串）。
- `evidence.py`：Evidence Viewer 資料。資料日期為從網址或內文（含民國年）推測的最近日期，不是發布日期，找不到則顯示「日期不明」；內容摘錄取網頁前 500 字；列出報告中連結該來源的段落。沒有引用連結的段落中，含數字（%、億、萬、元等）的句子或表格列會自動加上「〔待驗證〕」，模型自行標註者一併計數。此為規則判斷，有引用不代表內容已被來源證實。
- 寫作品質要求（`research_agent.py` 的 `QUALITY_RULES`，市場研究與公司分析共用）：引用放在所支持的句子裡、數字寫清單位／幣別／地區／年份、關鍵數字盡量以兩個不同網站交叉佐證（只有一個來源時註明「（單一來源）」）、來源矛盾時並列說明、推論句以「研判」「推估」開頭，並附好／壞寫法範例。
- 引用查證（2026-10-29 新增）：報告寫完後，把每一則有引用的句子或表格列（最多 40 則）連同所引用網頁原文中、該句數字附近的摘錄，一次送給 FAST_LLM 判斷「支持／不支持／無法判斷」。不支持的句子加上「〔待驗證〕」並計入待驗證項目；報告開頭會註明比對了幾則、幾則不符。每次研究只多 1 次 Gemini 請求（使用 FAST_LLM 的額度）。查證失敗（額度用完、逾時、回覆格式不符）時報告照常完成，開頭註明「引用查證未完成」。在 `.env` 設 `VERIFY_CITATIONS=0` 可關閉。AI 查證本身也可能出錯，只是第二道防線，不能取代人工核對。
- 研究類型：「市場研究」（摘要、市場趨勢、競品分析、風險、結論與建議）或「公司分析」（公司基本資料、產品與技術、經營狀況、客戶與合作案例、競品比較、合作／加入評估、風險、查無公開資料）。公司分析要求優先引用經濟部商工登記，並把官網、LinkedIn、新聞稿標為「（自我宣稱）」。研究主題請寫公司中文全名並附統一編號或官網，避免查到同名公司（例如「Meta」會被當成 Meta Platforms）。
- 你的公司（GNTC）背景（選填，最多 2000 字）：只填自己公司的資料，被研究的公司寫在研究主題。市場研究會在「結論與建議」加入「市場切入建議」（目標客群、產品組合、差異化、定價與通路、90 天行動計畫、風險）；公司分析會加入「與我方公司比較及差異化策略」。公司背景只放進撰寫報告的提示，不放進網路搜尋查詢；引用公司背景的句子標示「〔公司背景〕」，不會被標為待驗證。最後使用的公司背景存於 SQLite，下次自動帶入，每筆研究歷史也會保存當次使用的版本。
- `history.py`：SQLite 研究歷史，存於 `data/research_history.db`（Git 忽略）。成功與失敗都會記錄；失敗只存已去除敏感內容的錯誤訊息。可在「研究歷史」重新開啟、下載或刪除。
- `registry.py`：經濟部商工登記開放資料（`data.gcis.nat.gov.tw`，免金鑰）。公司分析的研究主題含「統一編號 xxxxxxxx」或「統編 xxxxxxxx」時，研究前先查詢公司基本資料、董監事與營業項目，以「## 公司登記資料（官方）」表格放在報告最前面（不經 AI 改寫、不標〔待驗證〕），並交給 AI 要求以官方為準、指出網路資料的差異；Evidence Viewer 也會列出這筆官方來源。有限公司沒有實收資本額，顯示「不適用」。查詢失敗或查無資料時，報告開頭會註明，研究照常進行。登記資料存於研究歷史，競品監測會逐欄比對（名稱、狀態、資本額、代表人、地址、登記機關、最後核准變更日期、董監事、營業項目），列在變化摘要最前面的「登記資料異動」。研究頁與競品監測頁有「用公司名稱查統一編號」工具（只列核准設立的公司，英文品牌名通常查不到）。
- `research_config.json`：Tavily、繁體中文、keyword context filter、嵌入模型 `gemini-embedding-001`。三個研究角色分配到不同 Gemini 模型：FAST `gemini-flash-lite-latest`、SMART（撰寫報告）`gemini-3.7-flash`、STRATEGIC（規劃子查詢）`gemini-3.6-flash`。Gemini 免費額度依模型分開計算（2026-10-18 實測 `gemini-flash-latest` 即 `gemini-3.8-flash` 每日僅 20 次請求，一次研究就需十幾次），分散到不同模型可增加每日可執行的研究次數。固定版本模型日後可能下架（`gemini-2.5-flash` 已回傳 404），屆時改用 Google AI Studio 列出的可用模型。可在 .env 使用 FAST_LLM / SMART_LLM / STRATEGIC_LLM / EMBEDDING 覆寫，格式為 `google_genai:模型名稱`。免費版資料可能被 Google 用於改進產品，勿輸入機密。
- 額度用完：GPT Researcher 會吞掉模型錯誤並重試多次。`research_agent.py` 監看其日誌，偵測到每日額度用完（Google 要求等待超過 5 分鐘）時立即停止，並顯示「Gemini 免費額度已用完」及大約等待時間，不再誤報為 Tavily 或來源問題。
- GPT Researcher 0.16.1 已內建 Tavily HTTP 搜尋整合，不需要額外 tavily-python SDK；Gemini 透過 langchain-google-genai 串接，已明列於 requirements。
- 單次搜尋與寫作共用 900 秒期限。進度僅表示階段，無虛構逐秒百分比；底層搜尋執行緒與已發送請求可能在逾時後持續短暫執行及計費。
- GPT Researcher 的費用統計不是完整帳單，可能不包含搜尋或其他服務。
- 蒐集來源清單與報告實際引用分開呈現，下載檔案包含兩者。報告由模型生成，繁中與段落結構由明確 prompt 引導；資料不足會說明，仍需人工核對重大決策。
- 原有 app.py、research_agent.py、requirements.txt、.gitignore 已備份於 `backups/original/`（忽略 Git）；原有文件及 .env 保留。
- .gitignore 排除金鑰、secrets.toml、虛擬環境、快取與備份。沒有執行 Git 提交。

## 競品監測（Competitor Monitor）

- `monitor.py`：競品清單與監測紀錄（同一個 SQLite 檔的 `competitors`、`monitor_checks` 表）。每次更新以「公司分析」模式重新研究該公司（報告照常存入研究歷史），再與上一次成功的研究比較：
  - 新出現的來源：以網址比對，結果確定。
  - 變化摘要：以 FAST_LLM 模型比較新舊兩份報告，分「新聞與曝光、客戶與合作、產品與技術、人事與徵才、經營與財務、其他」列出變化，並區分【新事件】（日期在上次研究之後）與【新查到】（可能只是搜尋結果不同）。摘要失敗時改列新出現的來源，不顯示服務錯誤原文。
  - 第一次更新只建立比較基準；也可用 `monitor.add_baseline(競品 id, 研究歷史 id)` 以既有的公司分析當基準。
  - 到期判斷以最後一次成功更新起算；失敗不重置時間。每日額度用完時立即停止，其餘競品標為略過。
- Dashboard「競品監測」頁：新增、編輯、停用、刪除競品；「更新所有到期競品」或單家「立即更新」；變化時間軸可展開完整報告。刪除競品只刪監測紀錄，研究報告仍保留在研究歷史。
- 每家競品可設定「監測重點」：加進研究主題要求逐項查證（查不到寫「查無公開資料」），變化摘要也會多一個「監測重點」分類逐項比較。勾選「這是我方公司」時，研究不帶入「你的公司背景」（避免拿自己跟自己比較）。
- 已加入 GNTC（我方公司）：監測重點為產品化訊號，包括徵才結構（產品工程師與 FDE 的比例）、公開定價或試用、合作夥伴計畫、Connector 數量、Dcard 以外的具名客戶、資安認證進度、法人名稱與統一編號。GNTC 的法人名稱與統一編號官網未公開（2026-10-19 查詢），所以識別資訊只用文字註明母公司狄卡科技，不寫「統一編號」字樣，以免把母公司的登記資料當成 GNTC 的。
- 額度：更新一家約使用 10–15 次 Gemini 請求，免費額度每天約可更新 3–5 家。
- `monitor_cli.py`：命令列更新到期競品（`--all` 為全部啟用中的競品；`--log 檔案` 把輸出附加到檔案，排程在背景執行時使用，錯誤只寫去除敏感內容的訊息）。沒有到期或全部成功回傳 0，有失敗或略過回傳 1，缺金鑰回傳 2。

已於 2026-10-19 建立 Windows 排程「GNTC Competitor Monitor」：每週一 09:00 以 `pythonw.exe`（不跳出視窗）執行，紀錄附加到 `data\monitor.log`；錯過時間（關機）會在下次開機後補跑，最長執行 3 小時，不重複同時執行。只在使用者登入時執行，只讀取 `.env` 的金鑰。建立指令：

```powershell
$dir = 'C:\Users\mikelee\Desktop\GNTC Market Research\gntc-research'
$action = New-ScheduledTaskAction -Execute "$dir\.venv\Scripts\pythonw.exe" -Argument "`"$dir\monitor_cli.py`" --log `"$dir\data\monitor.log`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'GNTC Competitor Monitor' -Action $action -Trigger $trigger -Settings $settings
```

立即執行一次：`Start-ScheduledTask -TaskName 'GNTC Competitor Monitor'`；查看紀錄：`Get-Content -Encoding UTF8 data\monitor.log -Tail 30`；手動執行：`.\.venv\Scripts\python.exe monitor_cli.py`；移除排程：`Unregister-ScheduledTask -TaskName 'GNTC Competitor Monitor'`。

## 部署到 Streamlit Community Cloud（免費）

1. 用 GitHub Desktop「File → Add local repository」選這個資料夾，建立第一個 commit（`.gitignore` 已排除 `.env`、`data/`、`outputs/`、`backups/`、`.venv/`、`.vscode/`），再「Publish repository」到自己的 GitHub，建議勾選 **Private**。
2. 到 https://share.streamlit.io 用 GitHub 登入 →「Create app」→ 選這個 repository、branch `main`、Main file `app.py`。
3. 「Advanced settings」選 **Python 3.12**，Secrets 依 `.streamlit/secrets.toml.example` 填寫（至少 `GNTC_CLOUD = "1"`；Secrets 填了金鑰時必須同時設定 `APP_PASSWORD`）。
4. Deploy 後可在 App settings 自訂網址（`https://名稱.streamlit.app`）。之後 push 到 GitHub 會自動重新部署。

雲端版的限制：
- 根層級 Secrets 會成為環境變數；`app.py` 也會把 `GOOGLE_API_KEY`、`TAVILY_API_KEY`、`APP_PASSWORD`、`GNTC_CLOUD`、`SUPABASE_*` 從 `st.secrets` 複製到環境變數（已存在的不覆蓋）。
- 設定 `APP_PASSWORD` 後需輸入密碼才能使用（以 `hmac.compare_digest` 比對）。公開網址沒有密碼時，任何人都能用掉 Secrets 裡的 API 額度；不設密碼時建議 Secrets 不放金鑰，讓使用者在左側欄填自己的金鑰。
- 排查失敗：研究失敗時，錯誤訊息與錯誤類型顯示在狀態框外；完整 traceback（金鑰已遮蔽）寫入伺服器 Logs（Manage app → Logs）。左側欄「測試金鑰」：Gemini 只查詢模型清單（不耗額度），Tavily 執行一次搜尋（使用 1 次搜尋額度）。GPT Researcher 遇到無效的 Tavily 金鑰不會報錯，只會「找不到來源」，所以「未取得可用的網路來源」時請先測試金鑰。
- `GNTC_CLOUD = "1"` 時停用「儲存到 .env」（共用伺服器上會變成所有訪客的預設金鑰），並在側欄提示資料是暫存的。
- 檔案系統是暫存的：App 閒置休眠、重新啟動或重新部署後，SQLite 研究歷史、競品清單、公司背景會清空。要保留資料，請設定下方的 Supabase 備份。

### 用 Supabase 保留雲端資料（選用）

設定後，`cloud_store.py` 會在 App 啟動時從 Supabase Storage 下載資料庫檔，每次寫入（研究、刪除、競品清單、公司背景、監測更新）後再上傳一次。資料仍是同一個 SQLite 檔，不需要改資料表。

1. 到 https://supabase.com 建立免費專案（地區建議選 Tokyo 或 Singapore）。
2. 左側「Storage」→「New bucket」，名稱 `gntc`，**不要勾選 Public**。
3. 「Project Settings」→「API」複製 Project URL 與 `service_role`（或 Secret）金鑰，貼到 Streamlit Secrets 的 `SUPABASE_URL`、`SUPABASE_SERVICE_KEY`（範本見 `.streamlit/secrets.toml.example`），然後重新啟動 App。
4. 側欄顯示「會自動備份到 Supabase」就是成功了。

注意：
- `SUPABASE_SERVICE_KEY` 能讀寫整個 Supabase 專案，只放在 Streamlit Secrets，不可 commit；日誌中會被遮蔽。
- 啟動時下載失敗，側欄會顯示錯誤，而且本次**不會上傳**，避免空白資料庫覆蓋既有備份；修正設定後重新啟動 App 即可。
- 上傳失敗時資料仍保存在本次的暫存空間，下次寫入會再試一次。
- 免費專案連續約一週沒有使用可能被暫停，需到 Supabase 後台恢復（以官網說明為準）。
- 本機沒有設定 Supabase 時完全不受影響；本機與雲端的資料仍互不相通。
- 沒有 Windows 排程，競品監測需手動更新；本機與雲端的資料互不相通。
- 免費方案的 App 一段時間沒人使用會休眠，下次開啟時需等候喚醒。

## 測試

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_dashboard
uv --cache-dir .uv-cache pip check --python .venv/Scripts/python.exe
```

填入兩組金鑰後，可執行真實端到端驗證（會使用 Gemini 免費額度與 Tavily 搜尋額度）：

```powershell
.\.venv\Scripts\python.exe smoke_research.py "臺灣智慧農業感測器市場與三家主要競品"
```

報告存入 `outputs/smoke-report.md`（忽略 Git）。缺少金鑰時回傳 exit code 2，服務失敗回傳 1，成功回傳 0；不輸出金鑰或服務例外原文。

2026-10-18 本機結果：8 項測試通過，涵蓋成功研究串接、來源去重與網址過濾、缺金鑰、空主題、過長主題、無來源、空報告、逾時、401/403/429 錯誤訊息不洩密、真實 SDK 設定載入，以及 Streamlit AppTest 的選單、缺金鑰停用、送出、下載元件、session 保留與失敗清除。外部服務於這些測試中使用 mock，不能當作真實網路研究成功證明。205 個現有套件相容性檢查通過；Streamlit HTTP health 回應 200 / ok。

2026-10-18 已改用 Google Gemini 並以真實金鑰完成端到端研究。新增 Evidence Viewer、待驗證標示、研究歷史與執行時間後，19 項測試通過（含 evidence、SQLite 歷史與舊資料庫升級、公司背景、研究類型、歷史頁重新開啟與刪除）。修改前的檔案備份於 `backups/before-evidence-history/`。

本次已使用 `uv pip install --python .venv/Scripts/python.exe -r requirements.txt` 成功完成依賴安裝檢查（4 個直接依賴皆已存在，無需重新下載），再以 `uv pip check` 確認相容性。未驗證全新環境從 PyPI 下載安裝。此機器的 uv 位於 `C:\Users\mikelee\.local\bin\uv.exe`；若 PATH 尚未包含它，可用完整路徑執行。

SDK 初始化會提示缺少選用的 `langchain_mcp_adapters`；本專案使用 Tavily，沒有使用 MCP retriever。測試亦出現上游 langchain-community 棄用提示，不影響目前測試通過。

## API 查證來源

2026-10-18 對照官方文件與已安裝 0.16.1 方法簽名，採用：

```python
researcher = GPTResearcher(query=..., report_type='research_report', report_source='web', config_path=...)
await researcher.conduct_research()
report = await researcher.write_report(custom_prompt=...)
researcher.get_source_urls()
researcher.get_research_sources()
researcher.get_costs()
```

- [官方 Python 套件文件](https://docs.gptr.dev/docs/gpt-researcher/gptr/pip-package)
- [官方設定文件](https://docs.gptr.dev/docs/gpt-researcher/gptr/config)

網路限制使本機無法直接向 PyPI 查詢最新版號；此處固定使用經驗證的 0.16.1，不宣稱它為 PyPI 最新發行版。
