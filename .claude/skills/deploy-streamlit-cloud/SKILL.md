---
name: deploy-streamlit-cloud
description: 把這個專案的修改發布到 Streamlit Community Cloud：測試、commit、push 到 GitHub，並說明雲端 Secrets 設定。使用者說「commit」「push」「上傳 GitHub」「部署」「更新雲端版」，或問 Streamlit Cloud 的 Secrets、密碼、網址時使用。
---

# 發布到 Streamlit Community Cloud

Streamlit Cloud 監看 GitHub 的 `main` 分支：push 成功就會自動重新部署。所以「發布」就是一條 **閘門** 流程：每一步都過了才進下一步，任何一步卡住就停下來向使用者回報，不要跳過。

回覆使用者一律用臺灣繁體中文，遵守 `CLAUDE.md` 的用語。

## 步驟

1. **測試全綠。** 用專案的 venv 跑完整測試：
   ```powershell
   $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m unittest test_dashboard
   ```
   完成條件：輸出有 `OK`，而且測試數量不少於上次。系統的 `python` 是 3.9，會在匯入時出現 `TypeError: unsupported operand type(s) for |`，這不是測試失敗，是用錯了 Python。

2. **檢查要送出的內容。** 跑 `git status --short` 和 `git diff --stat`，逐一確認每個變更檔案都是這次要發布的。完成條件：
   - `.env`、`.streamlit/secrets.toml`、`data/`、`backups/`、`outputs/` 都沒有出現在變更清單裡（`.gitignore` 已經排除它們，出現了就表示規則被改壞了）。
   - 金鑰掃描沒有結果：
     ```powershell
     git grep -nI --untracked -E "AIza[0-9A-Za-z_-]{20,}|tvly-[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|sb_secret_[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{30,}\.eyJ"
     ```
     有結果就停下來，把檔名告訴使用者，不要顯示金鑰本身。

3. **Commit。** 只 `git add` 第 2 步確認過的檔案。訊息寫成一行摘要（臺灣繁體中文），結尾加上系統提醒給的 Co-Authored-By 行。
   這台電腦的 PowerShell 是 5.1，`git commit -F -` 搭配 here-string 不會把訊息從 stdin 傳過去，會出現 `pathspec ... did not match`。做法是先把訊息寫到 scratchpad 的檔案，再用 `git commit -F <檔案路徑>`。

4. **Push。** 使用者明確說了「push」「上傳」「部署」才執行 `git push`；只說「commit」就做到第 3 步，然後問要不要 push。完成條件：輸出有 `main -> main`。`rejected ... fetch first` 表示 GitHub 上有本機沒有的 commit：停下來說明，不要用 `--force`。

5. **回報。** 告訴使用者 commit 編號與訊息、push 結果，並提醒 Streamlit Cloud 會在一兩分鐘內自動重新部署。如果這次改了 `requirements.txt`，提醒重新部署會比較久，因為要重新安裝套件。

## 雲端設定（使用者問到時參考）

Repo 裡沒有真正的 Secrets；雲端生效的是 Streamlit Cloud 的 **App settings → Secrets**，使用者要自己在那裡修改，push 不會改到它。範本在 `.streamlit/secrets.toml.example`，以它為準。

- **Python 版本必須選 3.12**（Advanced settings，只能在建立 app 時選；選錯要刪掉 app 重建）。
- **`APP_PASSWORD` 的規則**：Secrets 裡的 `GOOGLE_API_KEY`／`TAVILY_API_KEY` 留空時可以不設密碼，訪客只能用自己的金鑰；只要填了金鑰，就必須設定 `APP_PASSWORD`，否則任何拿到網址的人都會用掉使用者的額度。
- **網址是永久的**，但大約 12 小時沒人使用會休眠，打開後按「Yes, get this app back up」等約 30 秒恢復。
- **雲端資料**：沒有設定 Supabase 時，`data/` 的研究歷史在重新啟動或休眠喚醒後清空；設定 `SUPABASE_URL`／`SUPABASE_SERVICE_KEY` 後會自動備份（步驟見 README「用 Supabase 保留雲端資料」）。雲端沒有每週自動排程，競品監測要手動按「更新」。
- 部署失敗時，請使用者從「Manage app」複製日誌貼上，並先確認日誌裡沒有金鑰。
