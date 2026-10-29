import hmac
import os
from datetime import datetime

import streamlit as st

import cloud_store
import history
import monitor
import registry
from evidence import PROFILE_MARK, UNVERIFIED
from research_agent import (KEY_NAMES, MODES, PROFILE_MAX_CHARS, QuotaExceededError, ResearchResult, error_message,
                            check_keys, format_duration, key_source, log_failure, missing_keys, research, save_keys_to_env,
                            use_api_keys)

PROFILE_PLACEHOLDER = ('例如：GNTC 是一家……（公司簡介）\n主要服務：……\n目標客戶：……\n'
                       '優勢與資源：講師、合作夥伴、既有客戶……\n限制：預算、團隊規模……\n目標：例如一年內……')


def render_result(result, topic, finished_at, key, company_profile='', mode='market'):
    st.subheader(topic)
    st.caption(f'{MODES.get(mode, mode)}　完成時間：' + finished_at.strftime('%Y-%m-%d %H:%M:%S'))
    if company_profile:
        with st.expander('本次使用的公司背景'):
            st.text(company_profile)
    cited = [s for s in result.sources if s.get('cited')]
    cols = st.columns(5)
    cols[0].metric('蒐集來源', len(result.sources))
    cols[1].metric('報告引用來源', len(cited))
    cols[2].metric('待驗證項目', result.unverified_count)
    cols[3].metric('執行時間', format_duration(result.duration_seconds))
    cols[4].metric('估計費用 (USD)', f'${result.costs:.4f}')
    st.caption(f'「{UNVERIFIED}」表示該數字或結論沒有對應引用，或經 AI 比對後引用來源不支持該陳述，請回查原始來源後再使用；'
               f'「{PROFILE_MARK}」表示內容來自你提供的公司背景。'
               '使用 Gemini 免費版時實際不收費；費用估計依 GPT Researcher 內建價目計算，可能不準確，且不含 Tavily 搜尋費用。')
    report_tab, evidence_tab = st.tabs(['研究報告', 'Evidence Viewer'])
    with report_tab:
        st.download_button('下載 Markdown 報告', result.report.encode('utf-8'),
                           file_name=f'GNTC_research_{finished_at:%Y%m%d_%H%M%S}.md', mime='text/markdown',
                           key=f'{key}_download')
        st.markdown(result.report)
    with evidence_tab:
        render_evidence(result.sources, key)


def render_evidence(sources, key):
    if not sources:
        st.info('沒有來源資料。')
        return
    only_cited = st.checkbox('只顯示報告中有引用的來源', key=f'{key}_only_cited')
    st.caption('資料日期為從網址或內文推測的最近日期，不一定是發布日期；「日期不明」表示找不到。'
               '內容摘錄來自網頁原文，屬未經驗證的外部資料。')
    shown = [s for s in sources if s.get('cited')] if only_cited else sources
    for i, source in enumerate(shown, 1):
        label = f'{i}. {source.get("title") or source["url"]}' + ('　✅ 報告已引用' if source.get('cited') else '')
        with st.expander(label):
            st.markdown(f'**網址：** [{source["url"]}]({source["url"]})')
            st.markdown(f'**資料日期（推測）：** {source.get("date") or "日期不明"}')
            if source.get('citations'):
                st.markdown('**報告中引用此來源的段落：**')
                for passage in source['citations']:
                    st.markdown('> ' + passage)
            else:
                st.caption('報告內文沒有直接連結此來源。')
            if source.get('excerpt'):
                st.markdown('**內容摘錄：**')
                st.text(source['excerpt'])


def page_research():
    st.header('Market Research')
    st.caption('透過 GPT Researcher、Google Gemini 與 Tavily 搜尋真實網路資料，產生附引用的繁體中文報告。')
    if missing:
        st.warning('尚未設定：' + '、'.join(missing) + '。請在左側欄「API Key」填寫。')
    st.info('研究通常需數分鐘，會使用 Gemini 免費額度與 Tavily 搜尋額度；進度顯示處理階段與已執行時間，並非剩餘時間估計。')
    with st.form('research_form'):
        mode = st.radio('研究類型', list(MODES), format_func=MODES.get, horizontal=True, key='research_mode',
                        help='市場研究：分析市場趨勢、競品與切入建議。公司分析：深入調查單一公司的登記資料、產品、經營、'
                             '客戶案例、合作／加入評估，並與你的公司比較。')
        topic = st.text_area('研究主題（必填）', placeholder='點這裡輸入或貼上研究主題（範例見下方）',
                             max_chars=4000, height=130,
                             help='公司分析請寫公司中文全名，並盡量附上統一編號或官網，避免查到同名公司。')
        st.caption('範例｜市場研究：臺灣 AI 智慧農業市場，主要競品、商業機會與導入風險　'
                   '｜公司分析：超智諮詢有限公司（統一編號 90372749，官網 meta-intelligence.tech）')
        profile = st.text_area('你的公司（GNTC）背景（選填）', value=saved_profile(), placeholder=PROFILE_PLACEHOLDER,
                               max_chars=PROFILE_MAX_CHARS, height=170,
                               help='請填寫自己公司（GNTC）的資料；要研究的對象公司請寫在「研究主題」。'
                                    '填寫後，市場研究會加入針對貴公司的市場切入建議；公司分析會加入與貴公司的比較及差異化策略。'
                                    '公司背景只作為建議依據，不會當作市場資料來源；會儲存在本機，下次自動帶入。')
        st.caption('⚠️ 這一欄只填 GNTC 自己的資料，不要貼上被研究公司的資料。')
        submitted = st.form_submit_button('開始 AI 研究', type='primary', disabled=bool(missing))
    if submitted:
        if not topic.strip():
            st.warning('請輸入研究主題。')
        else:
            profile = profile.strip()
            try:
                history.save_company_profile(profile)
            except Exception:
                st.warning('公司背景儲存失敗，本次研究仍會使用你輸入的內容。')
            run_research(topic.strip(), profile, mode)
    render_tax_id_lookup('research_lookup')
    result = st.session_state.get('result')
    if result:
        st.divider()
        render_result(result, st.session_state['topic'], st.session_state['finished_at'], 'current',
                      st.session_state.get('company_profile', ''), st.session_state.get('mode', 'market'))


def saved_profile():
    try:
        return history.get_company_profile()
    except Exception:
        return ''


def run_research(topic, company_profile='', mode='market'):
    # Remove stale output so failed research cannot appear to have succeeded.
    st.session_state.pop('result', None)
    started_at = datetime.now()
    bar = st.progress(0, text='準備研究')
    result = failure = None
    with st.status(f'正在進行{MODES[mode]}', expanded=True) as status:
        def progress(value, message):
            bar.progress(value, text=message)
            status.update(label=message)
            st.write(message)
        try:
            with use_api_keys(entered_keys()):
                result = research(topic, progress=progress, company_profile=company_profile, mode=mode)
        except Exception as exc:
            failure = exc
        finished_at = datetime.now()
        if failure is None:
            bar.progress(100, text='研究完成')
            status.update(label=f'研究完成（執行 {format_duration(result.duration_seconds)}）', state='complete',
                          expanded=False)
        else:
            bar.empty()
            status.update(label=f'研究失敗（執行 {format_duration((finished_at - started_at).total_seconds())}）',
                          state='error', expanded=False)
    if failure is not None:
        message = error_message(failure)
        log_failure(failure, entered_keys())
        # Shown outside the status box so it stays visible (and copyable) when the box is collapsed.
        st.error(message)
        st.caption(f'錯誤類型：{type(failure).__name__}。可按左側欄「測試金鑰」確認金鑰是否有效；'
                   '詳細紀錄（已遮蔽金鑰）在伺服器 Logs。')
        save_history(topic, 'failed', started_at, finished_at, error=message, company_profile=company_profile,
                     mode=mode)
        return
    st.session_state.update(result=result, topic=topic, finished_at=finished_at, company_profile=company_profile,
                            mode=mode)
    save_history(topic, 'success', started_at, finished_at, result=result, company_profile=company_profile, mode=mode)


def save_history(topic, status, started_at, finished_at, result=None, error='', company_profile='', mode='market'):
    try:
        history.save_run(topic, status, started_at, finished_at, result=result, error=error,
                         company_profile=company_profile, mode=mode)
    except Exception:
        st.warning('研究歷史儲存失敗，本次結果仍可在目前頁面查看與下載。')


def page_history():
    st.header('研究歷史')
    try:
        runs = history.list_runs()
    except Exception:
        st.error('無法讀取研究歷史資料庫。')
        return
    if not runs:
        st.info('尚無研究紀錄。完成一次研究後會自動儲存於此。')
        return
    labels = {run['id']: f'{run["started_at"].replace("T", " ")}　{"✅" if run["status"] == "success" else "❌"}　'
                         f'[{MODES.get(run["mode"], run["mode"])}]　'
                         f'{run["topic"][:60]}' for run in runs}
    run_id = st.selectbox('選擇研究紀錄', list(labels), format_func=labels.get)
    run = history.get_run(run_id)
    if run is None:
        st.warning('此紀錄已不存在。')
        return
    if run['status'] == 'success':
        result = ResearchResult(report=run['report'], sources=run['sources'], costs=run['costs'],
                                duration_seconds=run['duration_seconds'], unverified_count=run['unverified_count'])
        render_result(result, run['topic'], run['finished_at'], f'history_{run_id}', run['company_profile'], run['mode'])
    else:
        st.subheader(run['topic'])
        st.error(f'研究失敗：{run["error"]}')
        st.caption(f'開始：{run["started_at"]:%Y-%m-%d %H:%M:%S}　執行時間：{format_duration(run["duration_seconds"])}')
    st.divider()
    confirm = st.checkbox('確認刪除這筆紀錄', key=f'confirm_delete_{run_id}')
    if st.button('刪除紀錄', disabled=not confirm, key=f'delete_{run_id}'):
        history.delete_run(run_id)
        st.rerun()


def render_tax_id_lookup(key):
    with st.expander('🔍 用公司名稱查統一編號（經濟部商工登記）'):
        st.caption('公司分析與競品監測在研究主題或識別資訊中寫「統一編號 xxxxxxxx」，報告就會附上經濟部官方登記資料，'
                   '競品監測也會逐欄比對資本額、代表人、董監事等登記異動。')
        keyword = st.text_input('公司名稱關鍵字', key=f'{key}_keyword', placeholder='例如：愛卡拉、數據決策')
        if st.button('查詢', key=f'{key}_search'):
            try:
                results = registry.search_by_name(keyword)
            except ValueError as exc:
                st.warning(str(exc))
            except registry.RegistryError as exc:
                st.error(str(exc) + ' 請稍後再試，或直接到 findbiz.nat.gov.tw 查詢。')
            else:
                if results:
                    st.dataframe([{'統一編號': r['tax_id'], '公司名稱': r['name'], '狀態': r['status'],
                                   '代表人': r['responsible'], '所在地': r['address']} for r in results],
                                 hide_index=True, use_container_width=True)
                    st.caption('只列出「核准設立」狀態的公司，最多 20 筆。英文品牌名通常查不到，請改用中文公司名稱。')
                else:
                    st.info('查無符合的公司。英文品牌名通常查不到，請改用中文公司名稱的一部分。')


def page_monitor():
    st.header('競品監測')
    st.caption('定期以「公司分析」重新研究每家競品，並與上次結果比較，列出新聞、合作、產品、徵才與經營的變化。'
               '更新一家約使用 10–15 次 Gemini 請求，免費額度每天約可更新 3–5 家。')
    for kind, message in st.session_state.pop('monitor_messages', []):
        getattr(st, kind)(message)
    try:
        competitors = monitor.list_competitors()
    except Exception:
        st.error('無法讀取競品資料庫。')
        return
    with st.expander('新增競品', expanded=not competitors):
        with st.form('add_competitor', clear_on_submit=True):
            name = st.text_input('公司名稱（必填）', placeholder='例如：MaiAgent')
            identifiers = st.text_input('識別資訊', placeholder='例如：統一編號 90372749，官網 example.com')
            interval = st.number_input('監測頻率（天）', *monitor.INTERVAL_RANGE, value=7)
            notes = st.text_area('備註', height=70)
            focus = st.text_area('監測重點（選填）', height=70, help='每次更新都會要求研究逐項查證這些重點，變化摘要也會逐項比較。例如：公開定價、徵才結構、資安認證、具名客戶案例。')
            own = st.checkbox('這是我方公司（研究時不與「你的公司背景」比較）')
            if st.form_submit_button('新增'):
                try:
                    monitor.add_competitor(name, identifiers, notes, interval, focus, own)
                except ValueError as exc:
                    st.warning(str(exc))
                else:
                    st.rerun()
    render_tax_id_lookup('monitor_lookup')
    if not competitors:
        st.info('尚未設定競品。請先新增要追蹤的公司。')
        return

    due = [c for c in competitors if c['due']]
    st.dataframe([{'競品': c['name'], '識別資訊': c['identifiers'], '頻率（天）': c['interval_days'],
                   '狀態': '停用' if not c['active'] else ('到期' if c['due'] else '正常'),
                   '上次更新': (c['last_checked_at'] or '尚未更新').replace('T', ' '),
                   '上次結果': monitor.STATUS_LABELS.get(c['last_status'], '—')} for c in competitors],
                 hide_index=True, use_container_width=True)
    if st.button(f'更新所有到期競品（{len(due)} 家）', type='primary', disabled=not due or bool(missing),
                 key='update_due'):
        run_monitor_updates(due)

    st.divider()
    labels = {c['id']: c['name'] + ('（停用）' if not c['active'] else '') for c in competitors}
    competitor_id = st.selectbox('查看競品', list(labels), format_func=labels.get, key='monitor_selected')
    competitor = next(c for c in competitors if c['id'] == competitor_id)
    render_competitor(competitor)


def render_competitor(competitor):
    cid = competitor['id']
    left, right = st.columns([3, 1])
    with left:
        st.subheader(competitor['name'])
        if competitor['identifiers']:
            st.caption(competitor['identifiers'])
        if competitor['is_own_company']:
            st.caption('我方公司')
        if competitor['notes']:
            st.write(competitor['notes'])
        if competitor['focus']:
            st.markdown('**監測重點：** ' + competitor['focus'])
    with right:
        if st.button('立即更新', key=f'update_{cid}', disabled=bool(missing) or not competitor['active']):
            run_monitor_updates([competitor])
    with st.expander('編輯／停用／刪除'):
        with st.form(f'edit_competitor_{cid}'):
            name = st.text_input('公司名稱', competitor['name'])
            identifiers = st.text_input('識別資訊', competitor['identifiers'])
            interval = st.number_input('監測頻率（天）', *monitor.INTERVAL_RANGE, value=competitor['interval_days'])
            notes = st.text_area('備註', competitor['notes'], height=70)
            focus = st.text_area('監測重點（選填）', competitor['focus'], height=70, help='每次更新都會要求研究逐項查證這些重點，變化摘要也會逐項比較。例如：公開定價、徵才結構、資安認證、具名客戶案例。')
            own = st.checkbox('這是我方公司（研究時不與「你的公司背景」比較）', bool(competitor['is_own_company']))
            active = st.checkbox('啟用監測', bool(competitor['active']))
            if st.form_submit_button('儲存'):
                try:
                    monitor.update_competitor(cid, name, identifiers, notes, interval, active, focus, own)
                except ValueError as exc:
                    st.warning(str(exc))
                else:
                    st.rerun()
        confirm = st.checkbox('確認刪除這家競品與其監測紀錄（研究報告仍保留在研究歷史）', key=f'confirm_remove_{cid}')
        if st.button('刪除競品', disabled=not confirm, key=f'remove_{cid}'):
            monitor.delete_competitor(cid)
            st.rerun()

    checks = monitor.list_checks(cid)
    if not checks:
        st.info('尚無監測紀錄。按「立即更新」建立第一次比較基準。')
        return
    st.markdown('#### 變化時間軸')
    for i, check in enumerate(checks):
        label = f'{check["checked_at"].replace("T", " ")}　{monitor.STATUS_LABELS[check["status"]]}'
        if check['status'] == 'checked':
            label += f'　新來源 {len(check["new_sources"])} 個'
        with st.expander(label, expanded=i == 0):
            if check['status'] == 'failed':
                st.error(check['error'])
                continue
            st.markdown(check['summary'])
            if check['new_sources']:
                st.markdown('**本次新出現的來源：**')
                for source in check['new_sources']:
                    st.markdown(f'- [{source.get("title") or source["url"]}]({source["url"]})'
                                f'（{source.get("date") or "日期不明"}）')
            if check['run_id'] and st.checkbox(f'顯示完整報告（研究歷史第 {check["run_id"]} 筆）', key=f'report_{check["id"]}'):
                run = history.get_run(check['run_id'])
                if run:
                    st.markdown(run['report'])


def run_monitor_updates(competitors):
    messages = []
    for competitor in competitors:
        with st.status(f'更新 {competitor["name"]}', expanded=True) as status:
            def progress(value, message):
                status.update(label=f'{competitor["name"]}：{message}')
            try:
                with use_api_keys(entered_keys()):
                    monitor.run_check(competitor['id'], progress=progress)
            except QuotaExceededError as exc:
                status.update(label=f'{competitor["name"]}：失敗', state='error')
                messages.append(('error', f'{competitor["name"]}：{error_message(exc)} 其餘競品未更新。'))
                break
            except Exception as exc:
                log_failure(exc, entered_keys())
                status.update(label=f'{competitor["name"]}：失敗', state='error')
                messages.append(('error', f'{competitor["name"]}：{error_message(exc)}'))
            else:
                status.update(label=f'{competitor["name"]}：更新完成', state='complete', expanded=False)
                messages.append(('success', f'{competitor["name"]}：更新完成。'))
    st.session_state['monitor_messages'] = messages
    st.rerun()


def entered_keys():
    """API keys typed into the sidebar in this browser session (never shown again, not saved unless asked)."""
    return {name: st.session_state.get(f'key_input_{name}', '') for name in KEY_NAMES}


def save_entered_keys():
    try:
        saved = save_keys_to_env(entered_keys())
    except Exception:
        st.session_state['key_message'] = ('error', '儲存到 .env 失敗，請確認專案資料夾可寫入。')
        return
    if not saved:
        st.session_state['key_message'] = ('warning', '沒有可儲存的金鑰，請先在上方填寫。')
        return
    for name in saved:
        st.session_state[f'key_input_{name}'] = ''
    st.session_state['key_message'] = ('success', f'已將 {"、".join(saved)} 儲存到 .env，下次啟動會自動載入。')


def page_settings():
    st.subheader('API Key 設定')
    if CLOUD:
        st.markdown('''在左側欄「API Key」填寫自己的金鑰即可使用：
- 金鑰只在這次瀏覽中使用，不寫入任何檔案；關閉或重新整理頁面後需要重新填寫。
- 留空時沿用管理者在 Streamlit Cloud「Secrets」設定的金鑰（如有）。
- 雲端版不提供「儲存到 .env」，也沒有每週自動排程；競品監測需手動按「更新」。''')
    else:
        st.markdown('''在左側欄「API Key」直接填寫自己的金鑰即可使用：
- **只填寫、不儲存**：金鑰只在這次瀏覽中使用，不寫入任何檔案；關閉或重新整理頁面後需要重新填寫。
- **按「儲存到 .env」**：寫入專案的 `.env` 檔，下次啟動自動載入。只在自己的電腦上使用，不要把 `.env` 分享或上傳。

填寫的金鑰優先於 `.env` 與環境變數。留空則沿用 `.env` 的設定。''')
    st.info('「✅」只代表已有設定值；金鑰是否有效，會在執行研究時由 Google 與 Tavily 驗證。'
            '多人同時使用同一台伺服器時，研究會依序執行，避免互相使用到對方的金鑰。')
    st.link_button('取得 Gemini API Key（Google AI Studio）', 'https://aistudio.google.com/apikey')
    st.link_button('取得 Tavily API Key', 'https://app.tavily.com/')
    backup_settings()


def backup_settings():
    st.subheader('Supabase 備份')
    if BACKUP == 'off':
        st.info('尚未設定。在 Secrets 設定 SUPABASE_URL 與 SUPABASE_SERVICE_KEY 後，研究歷史、競品清單與公司背景'
                '會備份到 Supabase，App 重新啟動後仍會保留（設定方式見 README）。')
        return
    if BACKUP == 'error':
        st.error('啟動時無法從 Supabase 還原，為了避免覆蓋既有備份，本次不會備份。請確認 Supabase 設定後重新啟動 App。')
        return
    if st.button('立即備份並檢查', key='backup_now'):
        with st.spinner('上傳到 Supabase…'):
            cloud_store.backup(history.DB_PATH)
    if cloud_store.last_error:
        st.error('最近一次備份失敗：' + cloud_store.last_error)
    if cloud_store.last_backup:
        done = cloud_store.last_backup
        st.success(f'最近一次備份：{done["at"]:%Y-%m-%d %H:%M:%S}（臺灣時間），{done["size"] / 1024:.1f} KB')
    elif not cloud_store.last_error:
        st.caption('App 這次啟動後還沒有備份。儲存研究、公司背景或競品清單時會自動備份，也可以按上方按鈕立即備份。')
    st.caption('啟動時已從 Supabase 還原既有備份。' if BACKUP == 'restored' else '啟動時 Supabase 上還沒有備份，從空白開始。')


def sidebar_backup_notice():
    if BACKUP == 'error':
        st.error('無法從 Supabase 還原研究歷史，本次不會備份，以免覆蓋既有備份。請確認 Supabase 設定後重新啟動 App。')
    elif BACKUP != 'off' and cloud_store.last_error:
        st.warning('最近一次備份到 Supabase 失敗，新資料目前只存在暫存空間：' + cloud_store.last_error)
    if BACKUP in ('restored', 'new'):
        st.caption('研究歷史、競品清單與公司背景會自動備份到 Supabase，App 重新啟動後仍會保留。'
                   '備份狀態見「API 設定」。')
    elif CLOUD:
        st.warning('雲端版的研究歷史、競品清單與公司背景存在暫存空間，App 重新啟動（例如閒置休眠、重新部署）後可能清空。'
                   '重要報告請下載保存。')


def load_streamlit_secrets():
    """Expose Streamlit secrets (Streamlit Community Cloud / .streamlit/secrets.toml) as environment variables."""
    try:
        secrets = dict(st.secrets)
    except Exception:  # no secrets file: local use with .env
        return
    for name in (*KEY_NAMES, 'APP_PASSWORD', 'GNTC_CLOUD', *cloud_store.SETTING_NAMES):
        value = secrets.get(name)
        if isinstance(value, (str, int, bool)) and str(value).strip() and not os.getenv(name):
            os.environ[name] = str(value).strip()


def require_password():
    """When APP_PASSWORD is set (recommended for a public URL), ask for it before showing anything."""
    expected = os.getenv('APP_PASSWORD', '')
    if not expected or st.session_state.get('authenticated'):
        return
    st.title('GNTC AI Research Dashboard')
    with st.form('login'):
        password = st.text_input('請輸入使用密碼', type='password', key='login_password')
        submitted = st.form_submit_button('登入', type='primary')
    if submitted:
        if hmac.compare_digest(password.encode('utf-8'), expected.encode('utf-8')):
            st.session_state['authenticated'] = True
            st.rerun()
        st.error('密碼錯誤。')
    st.stop()


@st.cache_resource(show_spinner='正在從 Supabase 還原研究歷史…')
def start_cloud_backup():
    """Once per server process: restore the Supabase backup before anything reads the database."""
    return cloud_store.start()


st.set_page_config(page_title='GNTC AI Research Dashboard', page_icon='🔎', layout='wide')
load_streamlit_secrets()
# Cloud mode: shared server with a temporary file system.
CLOUD = os.getenv('GNTC_CLOUD', '').strip().lower() in ('1', 'true', 'yes')
SOURCE_TEXT = {'session': '本次填寫', 'env': '雲端 Secrets' if CLOUD else '.env／環境變數'}
BACKUP = start_cloud_backup()
require_password()
with st.sidebar:
    st.title('GNTC Workspace')
    page = st.radio('功能選單', ['Market Research', '研究歷史', '競品監測', 'API 設定'], key='page')
    st.divider()
    st.markdown('**API Key**')
    for name in KEY_NAMES:
        st.text_input(name, type='password', key=f'key_input_{name}', placeholder='貼上金鑰（留空沿用 .env）',
                      autocomplete='off')
    missing = missing_keys(entered_keys())
    for name in KEY_NAMES:
        source = key_source(name, entered_keys())
        st.write(f'✅ {name}（{SOURCE_TEXT[source]}）' if source else f'❌ {name}（未設定）')
    if st.button('測試金鑰', key='check_keys', disabled=len(missing) == len(KEY_NAMES),
                 help='Gemini 只查詢模型清單（不消耗額度）；Tavily 會執行一次搜尋（使用 1 次搜尋額度）。'):
        with st.spinner('測試中…'):
            for name, (ok, message) in check_keys(entered_keys()).items():
                (st.success if ok else st.error if ok is False else st.warning)(f'{name}：{message}')
    if CLOUD:
        # On a shared server a saved key would become every visitor's default key.
        st.caption('雲端版不提供「儲存到 .env」；填寫的金鑰只在這次瀏覽中使用。')
    else:
        st.button('儲存到 .env', on_click=save_entered_keys, key='save_keys',
                  disabled=not any(value.strip() for value in entered_keys().values()))
    if 'key_message' in st.session_state:
        kind, message = st.session_state.pop('key_message')
        getattr(st, kind)(message)
    st.caption('不會顯示已儲存的金鑰內容。')

st.title('GNTC AI Research Dashboard')
if page == 'API 設定':
    page_settings()
elif page == '研究歷史':
    page_history()
elif page == '競品監測':
    page_monitor()
else:
    page_research()
# After the page ran, so a backup that failed during this run is reported at once.
with st.sidebar:
    sidebar_backup_notice()
