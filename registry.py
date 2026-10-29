"""Official company registration data from the Ministry of Economic Affairs open data API (no key needed)."""
import re
from datetime import date

import httpx

API_BASE = 'https://data.gcis.nat.gov.tw/od/data/api/'
DATASETS = {
    'basic': '5F64D864-61CB-4D0D-8AD9-492047CC1EA6',      # 公司登記基本資料
    'directors': '4E5F7653-1B91-4DDC-99D5-468530FAE396',  # 公司登記董監事資料
    'items': '236EE382-4942-41A9-BD03-CA0709025E7C',      # 公司登記營業項目
    'by_name': '6BBA2268-1367-4B42-9CCA-BC17499EBE8C',    # 公司名稱關鍵字查詢
}
SOURCE_URL = 'https://findbiz.nat.gov.tw/'
SOURCE_TITLE = '經濟部商工登記公示資料（官方開放資料 API 查詢）'
TIMEOUT_SECONDS = 20

_TAX_ID = re.compile(r'(?:統一編號|統編)\s*[:：]?\s*(\d{8})(?!\d)')
# Field label, record key. Changes in these fields are reported by the Competitor Monitor.
TRACKED_FIELDS = (('公司名稱', 'name'), ('登記狀態', 'status'), ('資本總額', 'capital'), ('實收資本額', 'paid_in_capital'),
                  ('代表人', 'responsible'), ('公司所在地', 'address'), ('登記機關', 'register_org'),
                  ('最後核准變更日期', 'change_date'))


class RegistryError(RuntimeError):
    """The registry API could not be reached or returned something unexpected."""


def extract_tax_id(text):
    match = _TAX_ID.search(text or '')
    return match.group(1) if match else None


def roc_to_iso(value):
    """'1110706' (ROC calendar) -> '2022-07-06'; '' -> None."""
    value = (value or '').strip()
    if not re.fullmatch(r'\d{6,7}', value):
        return None
    try:
        return date(int(value[:-4]) + 1911, int(value[-4:-2]), int(value[-2:])).isoformat()
    except ValueError:
        return None


def _get(dataset, odata_filter, top=50, client=None):
    params = {'$format': 'json', '$filter': odata_filter, '$skip': 0, '$top': top}
    try:
        response = (client or httpx).get(API_BASE + DATASETS[dataset], params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        if not response.content.strip():
            return []
        rows = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RegistryError('經濟部商工登記資料查詢失敗。') from exc
    if not isinstance(rows, list):
        raise RegistryError('經濟部商工登記資料格式不符。')
    return [row for row in rows if isinstance(row, dict)]


def is_limited_company(name):
    """有限公司 has no paid-in capital; only 股份有限公司 does."""
    return name.endswith('有限公司') and not name.endswith('股份有限公司')


def fetch_company(tax_id, client=None):
    """Registration record for an 8-digit tax ID, or None when no company is registered under it."""
    if not re.fullmatch(r'\d{8}', tax_id or ''):
        raise ValueError('統一編號必須是 8 位數字。')
    odata_filter = f'Business_Accounting_NO eq {tax_id}'
    basic = _get('basic', odata_filter, top=1, client=client)
    if not basic:
        return None
    row = basic[0]
    directors = _get('directors', odata_filter, client=client)
    items = _get('items', odata_filter, top=1, client=client)
    name = row.get('Company_Name') or ''
    record = {
        'tax_id': tax_id,
        'name': name,
        'status': row.get('Company_Status_Desc') or '',
        'capital': row.get('Capital_Stock_Amount'),
        'paid_in_capital': None if is_limited_company(name) else row.get('Paid_In_Capital_Amount'),
        'responsible': row.get('Responsible_Name') or '',
        'address': row.get('Company_Location') or '',
        'register_org': row.get('Register_Organization_Desc') or '',
        'setup_date': roc_to_iso(row.get('Company_Setup_Date')),
        'change_date': roc_to_iso(row.get('Change_Of_Approval_Data')),
        'revoke_date': roc_to_iso(row.get('Revoke_App_Date')),
        'suspend_begin': roc_to_iso(row.get('Sus_Beg_Date')),
        'suspend_end': roc_to_iso(row.get('Sus_End_Date')),
        'directors': [{'position': d.get('Person_Position_Name') or '', 'name': d.get('Person_Name') or '',
                       'juristic_person': d.get('Juristic_Person_Name') or '', 'shares': d.get('Person_Shareholding')}
                      for d in directors],
        'business_items': [{'code': i.get('Business_Item') or '', 'name': i.get('Business_Item_Desc') or ''}
                           for i in (items[0].get('Cmp_Business') or [] if items else [])],
        'fetched_on': date.today().isoformat(),
    }
    return record


def search_by_name(keyword, active_only=True, client=None):
    """Companies whose name contains the keyword (at most 20)."""
    keyword = re.sub(r"[\s']", '', keyword or '')
    if len(keyword) < 2:
        raise ValueError('請輸入至少 2 個字的公司名稱關鍵字。')
    odata_filter = f'Company_Name like {keyword}' + (' and Company_Status eq 01' if active_only else '')
    return [{'tax_id': row.get('Business_Accounting_NO') or '', 'name': row.get('Company_Name') or '',
             'status': row.get('Company_Status_Desc') or '', 'responsible': row.get('Responsible_Name') or '',
             'address': row.get('Company_Location') or '', 'capital': row.get('Capital_Stock_Amount')}
            for row in _get('by_name', odata_filter, top=20, client=client)]


def _money(value):
    return f'新臺幣 {value:,} 元' if isinstance(value, (int, float)) else '無資料'


def to_markdown(record):
    """Deterministic report section; values come straight from the registry and are not rewritten by the model."""
    paid_in = '不適用（有限公司無實收資本額）' if record['paid_in_capital'] is None else _money(record['paid_in_capital'])
    rows = [('統一編號', record['tax_id']), ('公司名稱', record['name']), ('登記狀態', record['status']),
            ('資本總額', _money(record['capital'])), ('實收資本額', paid_in), ('代表人', record['responsible']),
            ('公司所在地', record['address']), ('登記機關', record['register_org']),
            ('核准設立日期', record['setup_date'] or '無資料'), ('最後核准變更日期', record['change_date'] or '無資料')]
    if record['revoke_date']:
        rows.append(('撤銷／廢止日期', record['revoke_date']))
    if record['suspend_begin']:
        rows.append(('停業期間', f'{record["suspend_begin"]} 至 {record["suspend_end"] or "未定"}'))
    lines = [f'## 公司登記資料（官方）', '',
             f'資料來源：[{SOURCE_TITLE}]({SOURCE_URL})，查詢日期 {record["fetched_on"]}。以下內容由系統直接查詢，未經 AI 改寫。', '',
             '| 項目 | 登記內容 |', '| :--- | :--- |'] + [f'| {label} | {value} |' for label, value in rows]
    if record['directors']:
        lines += ['', '**董監事**', '', '| 職稱 | 姓名 | 所代表法人 | 持有股份／出資額 |', '| :--- | :--- | :--- | :--- |']
        for d in record['directors']:
            shares = f'{d["shares"]:,}' if isinstance(d['shares'], (int, float)) else '—'
            lines.append(f'| {d["position"]} | {d["name"]} | {d["juristic_person"] or "—"} | {shares} |')
    if record['business_items']:
        lines += ['', '**登記營業項目**：' + '、'.join(f'{i["name"]}（{i["code"]}）' for i in record['business_items'])]
    return '\n'.join(lines)


def source_entry(record):
    """Evidence Viewer entry for the registry lookup."""
    return {'url': SOURCE_URL, 'title': SOURCE_TITLE, 'date': record['fetched_on'],
            'excerpt': f'統一編號 {record["tax_id"]}，{record["name"]}，{record["status"]}，資本總額 {_money(record["capital"])}，'
                       f'代表人 {record["responsible"]}。',
            'cited': True, 'citations': ['公司登記資料（官方）']}


def compare(previous, current):
    """Human-readable changes between two registry records (empty list when nothing changed)."""
    changes = []
    for label, key in TRACKED_FIELDS:
        if previous.get(key) != current.get(key):
            old, new = previous.get(key), current.get(key)
            if key in ('capital', 'paid_in_capital'):
                old, new = _money(old) if old is not None else '不適用', _money(new) if new is not None else '不適用'
            changes.append(f'{label}：{old or "無資料"} → {new or "無資料"}')
    for label, key, fmt in (('董監事', 'directors', lambda d: f'{d["position"]} {d["name"]}'),
                            ('營業項目', 'business_items', lambda i: f'{i["name"]}（{i["code"]}）')):
        before = {fmt(x) for x in previous.get(key) or []}
        after = {fmt(x) for x in current.get(key) or []}
        if after - before:
            changes.append(f'{label}新增：' + '、'.join(sorted(after - before)))
        if before - after:
            changes.append(f'{label}移除：' + '、'.join(sorted(before - after)))
    return changes
