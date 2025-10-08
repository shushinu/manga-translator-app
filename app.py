import streamlit as st
# ✅ 一定要放在所有 st. 呼叫之前
st.set_page_config(page_title="翻譯支援測試app", layout="wide")

from openai import OpenAI
from PIL import Image
import io
import base64
import re
import requests
import urllib.parse
from supabase import create_client

from streamlit_js_eval import streamlit_js_eval
import json, uuid

# （可選）開啟除錯資訊
SHOW_DEBUG = False

# ===========================================
# === i18n：語言定義與文字資源
# ===========================================
LANGS = {"zh-Hant": "中文（繁體）", "zh-Hans": "中文（简体）"}

# 文字資源（只本地化 UI 與我們自有的模板/提示；不影響既有功能）
STRINGS = {
    "zh-Hant": {
        # App 與通用
        "app_title": "📘 漫畫翻譯支援工具 - 測試版",
        "lang_widget_label": "介面語言",
        "current_login": "目前登入：{name}（{email}）",
        "logout": "🔓 登出",
        # Sidebar
        "sidebar_header": "操作選單",
        "sidebar_choose": "請選擇操作步驟：",
        "menu_ocr": "STEP1:上傳圖片並辨識文字（OCR）",
        "menu_edit": "STEP2:修正辨識文字",
        "menu_translate": "STEP3:輸入提示並翻譯",
        "temp_label": "翻譯的創造性（temperature）",
        "temp_help": "值越高越自由、口語更活。一般預設數值為0.95，若你希望譯文更貼近原文語氣與內容，可將數值調低。若你希望譯文更自然、像人工翻譯一樣靈活，可將數值調高。",
        # 登入/註冊 UI
        "login_title": "📘 漫畫翻譯支援工具 - 測試版",
        "login_subtitle": "🔐 請先登入",
        "email": "Email",
        "password": "密碼",
        "btn_login": "登入",
        "btn_build_account": "建立新帳號",
        "btn_google_login": "使用 Google 登入",
        "register_page_title": "📘 漫畫翻譯支援工具 - 測試版",
        "register_header": "✨ 註冊新帳號",
        "reg_email": "Email（用來登入）",
        "reg_pw": "密碼（至少 6 字元）",
        "reg_pw2": "再次輸入密碼",
        "btn_register": "註冊並獲取認證郵件",
        "back_to_login": "← 回到登入",
        # Step1：角色註冊 + 上傳主圖 OCR
        "char_section_title": "👥 請登錄登場人物",
        "char_section_desc": "請依序輸入角色圖片、名稱、性格後再執行 OCR",
        "char_img_uploader": "登場人物圖片（一次一位）",
        "char_name": "名稱（例如：大雄）",
        "char_desc": "性格或特徵（例如：愛哭、懶散）",
        "btn_char_add": "➕ 登錄",
        "char_list_header": "#### ✅ 已註冊角色：",
        "btn_update": "🔁 更新（{name}）",
        "btn_delete": "❌ 刪除",
        "main_img_uploader": "📄 上傳漫畫圖片（JPEG/PNG）",
        "btn_run_ocr": "📄 執行辨識",
        "ocr_result_label": "已辨識文字（可於下一步修正）",
        # Step2：修正
        "edit_title": "🛠️ 修正辨識文字內容",
        "orig_image": "#### 📷 原始圖片",
        "corr_area": "#### ✏️ 修正區域",
        "corr_input_label": "請修正辨識結果（可換行）",
        "btn_save_corr": "💾 儲存修正內容",
        "saved_corr": "內容已儲存，可進一步進行翻譯。",
        # Step3：模板、提示、翻譯
        "translate_input_title": "🧩 漫畫翻譯參考資料輸入欄",
        "bg_title": "作品背景與風格",
        "bg_caption": "請描述故事的時代・舞台、文化風格與敘事特色。",
        "example": "📌 參考範例（點擊展開）",
        "char_traits_title": "角色個性・劇中經歷",
        "char_traits_caption": "以下欄位會根據一開始註冊的角色自動生成；顯示順序＝註冊順序。",
        "term_title": "該作品的特殊用語／道具",
        "term_caption": "請列出劇中出現的特殊道具或用語，以及翻譯建議。",
        "policy_title": "翻譯方針",
        "policy_caption": "請說明翻譯時應注意的語氣、對象、整體風格等原則。",
        "btn_save_and_build": "💾 儲存並產生提示內容",
        "custom_prompt_title": "🔧 自訂提示內容",
        "custom_prompt_input": "提示內容輸入：",
        "btn_save_prompt": "💾 儲存提示內容",
        "btn_run_translate": "執行翻譯",
        "translate_result": "翻譯結果",
        # 模板（第 3 階段）
        "tpl_background": """1. 故事發生在哪個年代？（例如：昭和50年代、1970年代、未來世界）
答：

2. 故事場景是什麼地方？（例如：東京郊區、小學生的家、學校）
答：

3. 這部作品的整體的氛圍是什麼？（例如：搞笑、溫馨感人、冒險）
答：

4. 主要讀者對象是誰？（例如：小學生、青少年、全年齡）
答：
""",
        "tpl_character": """1. 這角色本身是什麼樣的性格？（例如：外向活潑）
答：

2. 在本段故事中，這個角色經歷了什麼樣的事情？
答：

3. 承上題，對此他有哪些情緒變化？（例如：生氣、害怕、感動）
答：

4. 語尾語氣、表情、動作等是否需要特別注意？（例如：武士獨有的第一人稱「在下」等等）
答：
""",
        "tpl_terminology": """1. 這段故事中出現了哪些特殊道具或用語？（例如：任意門、竹蜻蜓、記憶麵包）
答：

2. 這些用語在原文是什麼？是片假名、漢字、還是平假名？
答：

3. 如何翻譯這些用語最自然？（例如：直譯、意譯、抑或是有特別的譯法）
答：

4. 該用語在台灣讀者之間有無普遍認知？是否有既定譯名？
答：
""",
# 在 STRINGS["zh-Hant"] 裡、緊接在 "tpl_terminology" 之後加入：
"tpl_policy": """1. 你希望翻譯的整體語氣是什麼？（例如：輕鬆幽默、溫柔體貼、嚴肅冷靜）
答：

2. 面對目標讀者（例如小學生），用詞上有哪些需要特別注意的地方？
答：

3. 是希望以直譯的方式盡可能地保留原文意義？還是以意譯的方式翻譯以確保譯文閱讀起來更自然？
答：

4. 是否有特別需要避免的語氣、詞彙或文化誤解？
答：
""",

        # 提示/規則（OCR 與翻譯）
        "ocr_system": """你是一位熟悉日本漫畫版面與閱讀順序的文字抽取助手。請從下方圖片中，只提取下列兩類文字：

1.漫畫的對話框（吹き出し）
2.漫格內的旁白／敘述框（矩形框、黑底或白底的敘述文字）
　（⚠️ 不是頁面標題、章節名或作者資訊）

🧩 規則：

1.閱讀順序：整頁 由右到左、由上到下。同一格內也依此排序。
2.說話者標示（每行一筆）：
    ・對話框：使用下方角色名單中的名字；無法判定時用「不明」。
    ・旁白／敘述框：一律使用「旁白」。
    ・群眾同時發言的泡泡可用「群眾」。
    ・以上三個保留名 「旁白／不明／群眾」允許不在下方名單內。
3.禁止使用未提供的人名或外語名（如 Nobita、のび太），但可使用前述保留名。
4.忽略：頁首／頁尾標題（例：章節名、系列名、作者名）、效果音（擬聲字）、註解、頁碼、裝飾文字。
5.無法辨識的字以「□」保留，不得自行補完或翻譯。
6.輸出格式（逐行）：
    ・角色名稱：台詞
角色名稱可為名單中的角色，也可為保留名「旁白／不明／群眾」。
📎 可用角色名單：
{charlist}
（另允許保留名：旁白／不明／群眾）
""",
        "ocr_charlist_empty": "（沒有角色名單，若無法判斷就寫『不明』）",
        "translate_system": (
            "你是專業的日文漫畫→台灣繁體中文譯者。請嚴格遵守：\n"
            "1) 只輸出最終譯文，不要重複或引用提示內容，也不要加任何解釋、標題、前後綴。\n"
            "2) 逐行翻譯並保留輸入的行序與說話者標記（若存在例如「大雄：…」）。\n"
            "3) 角色語氣要符合提供的角色說明；若角色說明為空或缺，保持自然中性語氣，不自行補完人物設定。\n"
            "4) 參考資料中如出現空白、模板佔位（例如「答：」但沒有內容），一律忽略，不得自行填寫或推測。\n"
            "5) 只翻譯對話框內文字；不要翻譯未包含在輸入中的旁白、效果音或額外情節。\n"
            "6) 優先產生自然、地道的台灣華語口吻；避免直譯腔與不自然詞彙。標點符號用台灣常見用法。\n"
            "7) 專有名詞與約定俗成譯名（若於提示中提供）請一致；未提供時採通行直譯或自然意譯，但不要加入譯註或括號說明。\n"
            "8) 如遇無法辨認或缺字，保留該處為「…」，不要臆測補寫。\n"
            "【輸出格式要求】純文字、只有譯文本身；若輸入是多行，就輸出等量多行；不要出現任何多餘符號或區段標題。"
        ),
        # 其他提示段落（組合 prompt）
        "combined_header": (
            "請根據下列參考資料，將提供的日文漫畫對白翻譯為自然、符合角色語氣的台灣繁體中文。"
            "請特別注意情感、語氣、時代背景、人物性格與專業用語的使用。"
        ),
        "sec_background": "【作品背景與風格】\n{content}\n\n",
        "sec_terminology": "【專業術語／用語習慣】\n{content}\n\n",
        "sec_policy": "【翻譯方針】\n{content}\n\n",
        "sec_charblocks_title": "【角色補充】\n",
        "charblock": "【{name} 角色資訊】\n{content}\n",
        "sec_source": "【原始對白】\n{source}",
        # 其他訊息（可保留繁體，不是必要）
        "supabase_ok": "✅ Supabase 連線測試成功",
        "supabase_fail": "⚠️ Supabase 連線檢查失敗：{err}",
    },
    "zh-Hans": {
        "app_title": "📘 漫画翻译支援工具 - 测试版",
        "lang_widget_label": "界面语言",
        "current_login": "当前登录：{name}（{email}）",
        "logout": "🔓 登出",
        "sidebar_header": "操作选单",
        "sidebar_choose": "请选择操作步骤：",
        "menu_ocr": "STEP1:上传图片并识别文字（OCR）",
        "menu_edit": "STEP2:修正识别文字",
        "menu_translate": "STEP3:输入提示并翻译",
        "temp_label": "翻译的创造性（temperature）",
        "temp_help": "值越高越自由、口语更活。一般预设数值为0.95，若你希望译文更贴近原文语气与内容，可将数值调低。若你希望译文更自然、像人工翻译一样灵活，可将数值调高。",
        "login_title": "📘 漫画翻译支援工具 - 测试版",
        "login_subtitle": "🔐 请先登录",
        "email": "Email",
        "password": "密码",
        "btn_login": "登录",
        "btn_build_account": "建立新账号",
        "btn_google_login": "使用 Google 登录",
        "register_page_title": "📘 漫画翻译支援工具 - 测试版",
        "register_header": "✨ 注册新账号",
        "reg_email": "Email（用于登录）",
        "reg_pw": "密码（至少 6 个字符）",
        "reg_pw2": "再次输入密码",
        "btn_register": "注册并获取认证邮件",
        "back_to_login": "← 返回登录",
        "char_section_title": "👥 请登记登场人物",
        "char_section_desc": "请依序输入角色图片、名称、性格后再执行 OCR",
        "char_img_uploader": "登场人物图片（一次一位）",
        "char_name": "名称（例如：大雄）",
        "char_desc": "性格或特征（例如：爱哭、懒散）",
        "btn_char_add": "➕ 登记",
        "char_list_header": "#### ✅ 已登记角色：",
        "btn_update": "🔁 更新（{name}）",
        "btn_delete": "❌ 删除",
        "main_img_uploader": "📄 上传漫画图片（JPEG/PNG）",
        "btn_run_ocr": "📄 执行识别",
        "ocr_result_label": "已识别文字（可于下一步修正）",
        "edit_title": "🛠️ 修正识别文字内容",
        "orig_image": "#### 📷 原始图片",
        "corr_area": "#### ✏️ 修正区域",
        "corr_input_label": "请修正识别结果（可换行）",
        "btn_save_corr": "💾 保存修正内容",
        "saved_corr": "内容已保存，可进一步进行翻译。",
        "translate_input_title": "🧩 漫画翻译参考资料输入栏",
        "bg_title": "作品背景与风格",
        "bg_caption": "请描述故事的时代・舞台、文化风格与叙事特色。",
        "example": "📌 参考范例（点击展开）",
        "char_traits_title": "角色个性・剧中经历",
        "char_traits_caption": "以下栏位会根据一开始登记的角色自动生成；显示顺序＝登记顺序。",
        "term_title": "该作品的特殊用语／道具",
        "term_caption": "请列出剧中出现的特殊道具或用语，以及翻译建议。",
        "policy_title": "翻译方针",
        "policy_caption": "请说明翻译时应注意的语气、对象、整体风格等原则。",
        "btn_save_and_build": "💾 保存并生成提示内容",
        "custom_prompt_title": "🔧 自订提示内容",
        "custom_prompt_input": "提示内容输入：",
        "btn_save_prompt": "💾 保存提示内容",
        "btn_run_translate": "执行翻译",
        "translate_result": "翻译结果",
        "tpl_background": """1. 故事发生在哪个年代？（例如：昭和50年代、1970年代、未来世界）
答：

2. 故事场景是什么地方？（例如：东京郊区、小学生的家、学校）
答：

3. 这部作品的整体氛围是什么？（例如：搞笑、温馨感人、冒险）
答：

4. 主要读者对象是谁？（例如：小学生、青少年、全年龄）
答：
""",
        "tpl_character": """1. 这个角色本身是什么样的性格？（例如：外向活泼）
答：

2. 在本段故事中，这个角色经历了什么样的事情？
答：

3. 承上题，对此他有哪些情绪变化？（例如：生气、害怕、感动）
答：

4. 语尾语气、表情、动作等是否需要特别注意？（例如：武士独有的第一人称“在下”等等）
答：
""",
        "tpl_terminology": """1. 这段故事中出现了哪些特殊道具或用语？（例如：任意门、竹蜻蜓、记忆面包）
答：

2. 这些用语在原文是什么？是片假名、汉字、还是平假名？
答：

3. 如何翻译这些用语最自然？（例如：直译、意译、抑或是有特别的译法）
答：

4. 该用语在台湾读者之间有无普遍认知？是否有既定译名？
答：
""",
# 在 STRINGS["zh-Hans"] 裡、緊接在 "tpl_terminology" 之後加入：
"tpl_policy": """1. 你希望翻译的整体语气是什么？（例如：轻松幽默、温柔体贴、严肃冷静）
答：

2. 面对目标读者（例如小学生），用词上有哪些需要特别注意的地方？
答：

3. 是希望以直译的方式尽可能地保留原文意义？还是以意译的方式翻译以确保译文读起来更自然？
答：

4. 是否有特别需要避免的语气、词汇或文化误解？
答：
""",

        "ocr_system": """你是一位熟悉日本漫画版面与阅读顺序的文字抽取助手。请从下方图片中，只提取下列两类文字：

1.漫画的对话框（吹き出し）
2.漫格内的旁白／叙述框（矩形框、黑底或白底的叙述文字）
　（⚠️ 不是页面标题、章节名或作者资讯）

🧩 规则：

1.阅读顺序：整页 由右到左、由上到下。同一格内也依此排序。
2.说话者标示（每行一笔）：
    ・对话框：使用下方角色名单中的名字；无法判定时用「不明」。
    ・旁白／叙述框：一律使用「旁白」。
    ・群众同时发言的泡泡可用「群众」。
    ・以上三个保留名 「旁白／不明／群众」允许不在下方名单内。
3.禁止使用未提供的人名或外语名（如 Nobita、のび太），但可使用前述保留名。
4.忽略：页首／页尾标题（例：章节名、系列名、作者名）、效果音（拟声字）、註解、页码、装饰文字。
5.无法辨识的字以「□」保留，不得自行补完或翻译。
6.输出格式（逐行）：
    ・角色名称：台词
角色名称可为名单中的角色，也可为保留名「旁白／不明／群众」。
📎 可用角色名单：
{charlist}
（另允许保留名：旁白／不明／群众）
""",
        "ocr_charlist_empty": "（没有角色名单，若无法判断就写『不明』）",
        "translate_system": (
            "你是专业的日文漫画→简体中文译者。请严格遵守：\n"
            "1) 只输出最终译文，不要重复或引用提示内容，也不要加任何解释、标题、前后缀。\n"
            "2) 逐行翻译并保留输入的行序与说话者标记（若存在例如「大雄：…」）。\n"
            "3) 角色语气要符合提供的角色说明；若角色说明为空或缺，保持自然中性语气，不自行补完人物设定。\n"
            "4) 参考资料中如出现空白、模板占位（例如「答：」但没有内容），一律忽略，不得自行填写或推测。\n"
            "5) 只翻译对话框内文字；不要翻译未包含在输入中的旁白、效果音或额外情节。\n"
            "6) 优先产生自然、地道的简体中文口吻；标点符号用简体中文常见用法。\n"
            "7) 专有名词与约定俗成译名（若于提示中提供）请一致；未提供时采通行直译或自然意译，但不要加入译注或括号说明。\n"
            "8) 如遇无法辨认或缺字，保留该处为「…」，不要臆测补写。\n"
            "【输出格式要求】纯文字、只有译文本身；若输入是多行，就输出等量多行；不要出现任何多余符号或区段标题。"
        ),
        "combined_header": (
            "请根据下列参考资料，将提供的日文漫画对白翻译为自然、符合角色语气的简体中文。"
            "请特别注意情感、语气、时代背景、人物性格与专业用语的使用。"
        ),
        "sec_background": "【作品背景与风格】\n{content}\n\n",
        "sec_terminology": "【专业术语／用语习惯】\n{content}\n\n",
        "sec_policy": "【翻译方针】\n{content}\n\n",
        "sec_charblocks_title": "【角色补充】\n",
        "charblock": "【{name} 角色资讯】\n{content}\n",
        "sec_source": "【原始对白】\n{source}",
        "supabase_ok": "✅ Supabase 连接测试成功",
        "supabase_fail": "⚠️ Supabase 连接检查失败：{err}",
    },
}

def _get_lang_from_qs_or_session():
    qp = st.query_params
    # 認可的 lang
    if "lang" in qp and qp["lang"] in LANGS:
        st.session_state["lang"] = qp["lang"]
    if "lang" not in st.session_state:
        st.session_state["lang"] = "zh-Hant"
    return st.session_state["lang"]

def t(key: str) -> str:
    lang = st.session_state.get("lang", "zh-Hant")
    return STRINGS.get(lang, STRINGS["zh-Hant"]).get(key, STRINGS["zh-Hant"].get(key, key))

def _set_query_lang(lang: str):
    # 只更新 lang，不觸動其他參數
    st.query_params["lang"] = lang

# ===========================================
# 初始化 Supabase（使用 cache_resource，避免重複連線）
# ===========================================
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

sb = get_supabase()

# 🔸新增：確保健康檢查用 anon key，避免吃到過期的使用者 JWT
sb.postgrest.auth(st.secrets["supabase"]["anon_key"])

# 啟動時做輕量健康檢查
try:
    sb.table("translation_logs").select("id").limit(1).execute()
    if SHOW_DEBUG:
        st.write(t("supabase_ok"))
except Exception as e:
    st.warning(t("supabase_fail").format(err=e))

# ===========================================
# OpenAI 初始化
# ===========================================
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

# ===========================================
# Helper
# ===========================================

# 建議做命名空間前綴，避免跟其他專案/頁面衝突
APP_LS_PREFIX = "mtl:v1:"

def _ls_key(name: str) -> str:
    return f"{APP_LS_PREFIX}{name}"

def ls_get(key: str, default=None):
    """從 localStorage 讀 JSON；不存在時回傳 default。"""
    val = streamlit_js_eval(
        js_expressions=f'JSON.parse(localStorage.getItem("{key}") ?? "null")',
        key=f"get_{key}",
        want_output=True
    )
    return default if val is None else val

def ls_set(key: str, value):
    """寫入 JSON 到 localStorage。"""
    payload = json.dumps(value, ensure_ascii=False)
    streamlit_js_eval(
        js_expressions=f'localStorage.setItem("{key}", JSON.stringify({payload}))',
        key=f"set_{key}"
    )

def ls_remove(key: str):
    streamlit_js_eval(
        js_expressions=f'localStorage.removeItem("{key}")',
        key=f"rm_{key}"
    )

# ========= 放在 Helper 區（ls_* 後面即可） =========
def ensure_stable_user_id():
    """
    兩段式握手：
    1) 先嘗試讀 cookie；若讀到 → 直接使用
    2) 讀不到且尚未嘗試過 → 讓前端先把「既有的 LS UID」寫回 cookie，並 stop 一次讓前端完成
    3) 下一輪還是讀不到 → 這才生成新 UUID，寫入 cookie + LS，然後 st.rerun()
    """
    # 已經有就直接用（避免重覆跑邏輯）
    if st.session_state.get("user_id"):
        return st.session_state["user_id"]

    # 讀 cookie（第一次渲染常常會回 None/空字串）
    uid_from_cookie = streamlit_js_eval(
        js_expressions=(
            """
            (function() {
              const m = document.cookie.match(/(?:^|; )mtl_uid=([^;]+)/);
              return m ? decodeURIComponent(m[1]) : "";
            })()
            """
        ),
        key="uid_read_cookie",
        want_output=True,
    ) or ""

    if uid_from_cookie:
        st.session_state["user_id"] = uid_from_cookie
        st.session_state["_uid_src"] = "cookie"
        return uid_from_cookie

    # 還沒有 cookie → 第一次嘗試：把 LS 既有的 anon_user_id 寫回 cookie，然後停止本輪渲染
    if not st.session_state.get("_uid_stage1_tried"):
        st.session_state["_uid_stage1_tried"] = True

        # 從 LS 撈舊的 anon_user_id（如果本機之前用過就會有）
        legacy = ls_get(_ls_key("anon_user_id"))
        legacy = legacy if isinstance(legacy, str) and legacy.strip() else ""

        # 指示前端把 legacy 寫回 cookie（若沒有 legacy，只是做個 no-op，等下一輪進入 stage2）
        js = (
            f'document.cookie="mtl_uid={legacy}; Max-Age=315360000; path=/; SameSite=Lax";'
            if legacy else
            'void 0;'
        )
        streamlit_js_eval(js_expressions=js, key="uid_stage1_set_cookie")
        # 讓前端有時間寫入，這一輪先停；下一輪我們會再讀一次
        st.stop()

    # 第二輪仍讀不到 → 真的創建新 UUID，寫 cookie + LS，然後 rerun
    new_uid = str(uuid.uuid4())
    streamlit_js_eval(
        js_expressions=(
            f'document.cookie="mtl_uid={new_uid}; Max-Age=315360000; path=/; SameSite=Lax";'
            f'localStorage.setItem("{_ls_key("anon_user_id")}", "{new_uid}");'
        ),
        key="uid_stage2_set_cookie_and_ls"
    )
    st.session_state["user_id"] = new_uid
    st.session_state["_uid_src"] = "new"
    st.rerun()


# --- Cookie Helpers: 以 cookie 為主、localStorage 為輔 ---

# --- Cookie Helpers（host-only，最穩；不要設 domain） ---
def _js_set_cookie(name: str, value: str, days: int = 365):
    js = f"""
    (function(){{
      var d = new Date();
      d.setTime(d.getTime() + ({days}*24*60*60*1000));
      var expires = "expires="+ d.toUTCString();
      var secure = (location.protocol === 'https:') ? "; secure" : "";
      document.cookie = "{name}=" + encodeURIComponent("{value}") + ";" + expires + "; path=/" + "; samesite=Lax" + secure;
    }})();
    """
    streamlit_js_eval(js_expressions=js, key=f"set_cookie_{name}")

def _js_get_cookie(name: str):
    js = f"""
    (function(){{
      var nameEQ = "{name}" + "=";
      var ca = document.cookie.split(';');
      for(var i=0;i < ca.length;i++) {{
          var c = ca[i];
          while (c.charAt(0)==' ') c = c.substring(1,c.length);
          if (c.indexOf(nameEQ) == 0) return decodeURIComponent(c.substring(nameEQ.length,c.length));
      }}
      return null;
    }})();
    """
    return streamlit_js_eval(js_expressions=js, key=f"get_cookie_{name}", want_output=True)

def bind_textarea_with_ls(key: str, label: str, default_value: str, height: int = 200):
    """
    把 textarea 綁定到 localStorage，並且解決：
    1) streamlit_js_eval 首次渲染可能回 None 的問題
    2) 若 LS 有值、而 session_state 尚未載入，優先採用 LS 值
    """
    ls_key = _ls_key(key)

    # 這個旗標用來避免每次都覆蓋；只在第一次成功載入 LS 後打開
    loaded_flag = f"_ls_loaded::{key}"
    if loaded_flag not in st.session_state:
        st.session_state[loaded_flag] = False

    # 嘗試從 LS 讀（第一次可能是 None；之後通常會有值）
    ls_val = ls_get(ls_key)

    # 只有「尚未把 LS 載入過」時，才嘗試用 LS 覆蓋 session 的初值
    if not st.session_state[loaded_flag] and isinstance(ls_val, str) and ls_val != "":
        st.session_state[key] = ls_val
        st.session_state[loaded_flag] = True

    # 如果還沒有值（LS 也沒拿到），至少給一個 default
    if key not in st.session_state:
        st.session_state[key] = default_value

    def _on_change():
        ls_set(ls_key, st.session_state.get(key, ""))

    return st.text_area(label, key=key, height=height, on_change=_on_change)

# ---------- Storage Helpers（貼在 Helper 區，ls_* 之後即可） ----------
def _guess_image_mime(filename_or_bytes: str | bytes) -> str:
    try:
        return "image/png"
    except Exception:
        return "image/png"

def storage_upload_bytes(path: str, data: bytes, content_type: str = "image/png") -> str | None:
    """
    上傳 bytes 到 Supabase Storage 的 mtl bucket。
    先嘗試 upload（不帶 upsert，避免 storage3 的 header bool bug）；
    若檔名已存在造成 409，改用 update 覆蓋。
    回傳 public URL（bucket 設為 Public）。
    """
    bucket = "mtl"
    try:
        # ① 先試 upload（不帶 upsert，避免 bool header）
        resp = sb.storage.from_(bucket).upload(
            path=path,
            file=data,
            file_options={"contentType": content_type}  # 不要帶 upsert
        )
    except Exception as e:
        msg = str(e)
        if "409" in msg or "already exists" in msg.lower():
            try:
                resp = sb.storage.from_(bucket).update(
                    path=path,
                    file=data,
                    file_options={"contentType": content_type}
                )
            except Exception as e2:
                st.error(f"❌ Storage 覆蓋失敗：{e2}")
                return None
        else:
            st.error(f"❌ Storage 上傳失敗：{e}")
            return None

    # ③ 取得 public URL（Public bucket）
    try:
        url = sb.storage.from_(bucket).get_public_url(path)
        return url
    except Exception as e:
        st.error(f"❌ 取得 Public URL 失敗：{e}")
        return None


def _make_user_scoped_path(user_id: str, subpath: str) -> str:
    # e.g. users/<uid>/<subpath>
    return f"users/{user_id}/{subpath}"
# ---------- Storage Helpers end ----------

# --- Cookie Helpers: 以 cookie 為主、localStorage 為輔 ---


# ===========================================
# 🔐 混合登入（Authorization Code + PKCE）
# ===========================================
def _set_sb_auth_with_token(token: str):
    try:
        sb.postgrest.auth(token)
    except Exception:
        pass

def _fetch_supabase_user(access_token: str) -> dict:
    resp = requests.get(
        f"{st.secrets['supabase']['url']}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": st.secrets["supabase"]["anon_key"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

def _user_from_auth(auth_user: dict, access_token: str, provider: str) -> dict:
    full_name = (auth_user.get("user_metadata") or {}).get("full_name") or auth_user.get("email", "Guest")
    return {
        "id": auth_user.get("id"),
        "email": auth_user.get("email"),
        "full_name": full_name,
        "provider": provider,
        "access_token": access_token,
    }

def _b64url_encode(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def _sha256_b64url(text: str) -> str:
    import hashlib
    return _b64url_encode(hashlib.sha256(text.encode()).digest())

def _make_pkce_pair():
    import os
    verifier = _b64url_encode(os.urandom(32))
    challenge = _sha256_b64url(verifier)
    return verifier, challenge

def _exchange_code_for_session(auth_code: str, code_verifier: str, redirect_uri: str | None = None) -> dict:
    url = f"{st.secrets['supabase']['url']}/auth/v1/token?grant_type=pkce"
    headers = {
        "apikey": st.secrets["supabase"]["anon_key"],
        "Authorization": f"Bearer {st.secrets['supabase']['anon_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "auth_code": auth_code,
        "code_verifier": code_verifier,
    }
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri

    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code != 200:
        raise Exception(f"{r.status_code} {r.text}")
    return r.json()

# === i18n：右上角語言切換（登入前也顯示）
_get_lang_from_qs_or_session()

if st.session_state["lang"] == "zh-Hans":
    st.markdown("""
    <!-- 主：SC；後備：TC/JP，用於缺字時回退，避免樣式不一致 -->
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
          --cn-body: 500;   /* 正文 */
          --cn-heading: 700;/* 標題 */
          --cn-font: 'Noto Sans SC','Noto Sans TC','Noto Sans JP',
                      'Source Han Sans SC','PingFang SC',
                      'Microsoft YaHei UI','Microsoft YaHei',sans-serif;
        }
        /* 一次性套到整個 App（含所有子元件） */
        .stApp, .stApp * {
          font-family: var(--cn-font) !important;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
          text-rendering: optimizeLegibility;
          font-weight: var(--cn-body);
        }
        h1, h2, h3, h4, h5, h6,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
          font-weight: var(--cn-heading) !important;
        }
        /* 讓 Emoji 用彩色字型 */
        .stApp .emoji, .stApp [aria-label="emoji"] {
          font-family: 'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif !important;
          font-weight: 400 !important;
        }
        div.block-container{padding-top: 1.2rem;}
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- （可選）也補一條 JP 作為少數日文假名的保底 -->
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
          --tc-body: 500;
          --tc-heading: 700;
          --tc-font: 'Noto Sans TC','Noto Sans JP',
                     'Microsoft JhengHei','PingFang TC',sans-serif;
        }
        .stApp, .stApp * {
          font-family: var(--tc-font) !important;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
          text-rendering: optimizeLegibility;
          font-weight: var(--tc-body);
        }
        h1, h2, h3, h4, h5, h6,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
          font-weight: var(--tc-heading) !important;
        }
        .stApp .emoji, .stApp [aria-label="emoji"] {
          font-family: 'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif !important;
          font-weight: 400 !important;
        }
        div.block-container{padding-top: 1.2rem;}
    </style>
    """, unsafe_allow_html=True)


# 放在頁面最上方，靠右但不與原生頂欄重疊
_lang_cols = st.columns([0.78, 0.22])
with _lang_cols[1]:
    _cur = st.session_state["lang"]
    _new = st.selectbox(
        t("lang_widget_label"),
        options=list(LANGS.keys()),
        index=list(LANGS.keys()).index(_cur),
        format_func=lambda x: LANGS[x],
        key="lang_select",
    )
    if _new != _cur:
        st.session_state["lang"] = _new
        _set_query_lang(_new)
        st.rerun()

def auth_gate(require_login: bool = True):
    """門神：Google（Code+PKCE）＋ Email/密碼。"""
    qp = st.query_params

    # A) OAuth 回來
    if "code" in qp:
        code = qp.get("code")
        verifier = qp.get("pv", "")
        # === lang 保留：從 qs 讀 lang 值
        current_lang = qp.get("lang", st.session_state.get("lang", "zh-Hant"))

        redirect_url = (st.secrets.get("app", {}) or {}).get("redirect_url", "http://localhost:8501/")
        if not redirect_url.endswith("/"):
            redirect_url += "/"
        sep = "&" if ("?" in redirect_url) else "?"
        redirect_with_pv = f"{redirect_url}{sep}pv={urllib.parse.quote(verifier)}&lang={urllib.parse.quote(current_lang)}"

        if not verifier:
            st.error("OAuth 回來缺少 verifier（pv），請重試。")
        else:
            try:
                data = _exchange_code_for_session(code, verifier, redirect_with_pv)
                access_token = data.get("access_token")
                user_json = data.get("user") or {}
                if not access_token:
                    st.error(f"交換 access_token 失敗：{data}")
                else:
                    st.session_state["user"] = _user_from_auth(user_json, access_token, provider="google")
                    _set_sb_auth_with_token(access_token)
                    # === lang 保留：清除 code/pv 等，但保留 lang
                    keys_to_remove = ["code", "pv", "error", "error_description"]
                    for k in list(st.query_params.keys()):
                        if k in keys_to_remove:
                            try:
                                del st.query_params[k]
                            except Exception:
                                pass
                    _set_query_lang(current_lang)
                    st.rerun()
            except Exception as e:
                st.error(f"交換 access_token 發生錯誤：{e}")

    elif "error" in qp:
        st.warning(qp.get('error_description', qp.get('error')))
        # === lang 保留：只移除錯誤參數
        for k in ["error", "error_description"]:
            if k in st.query_params:
                try:
                    del st.query_params[k]
                except Exception:
                    pass

    # B) 未登入 → 登入／註冊 UI
    if "user" not in st.session_state:
        # 永遠先切回 anon key，避免沿用過期 JWT
        try:
            sb.postgrest.auth(st.secrets["supabase"]["anon_key"])
        except Exception:
            pass

        # ---- 共用：基本 URL、PKCE、兩個動作的連結 ----
        verifier, challenge = _make_pkce_pair()

        base_url = (st.secrets.get("app", {}) or {}).get("redirect_url", "http://localhost:8501/")
        if not base_url.endswith("/"):
            base_url += "/"
        join = "&" if ("?" in base_url) else "?"
        # === lang 保留：register 頁也跟著帶 lang
        register_url = f"{base_url}{join}register=1&lang={urllib.parse.quote(st.session_state['lang'])}"

        pv_join = "&" if ("?" in base_url) else "?"
        # 將 verifier 與 lang 塞到 redirect_to（PKCE 必要 + 語言保留）
        redirect_with_pv = (
            f"{base_url}{pv_join}"
            f"pv={urllib.parse.quote(verifier)}&lang={urllib.parse.quote(st.session_state['lang'])}"
        )

        google_login_url = (
            f"{st.secrets['supabase']['url']}/auth/v1/authorize"
            f"?provider=google"
            f"&response_type=code"
            f"&code_challenge={urllib.parse.quote(challenge)}"
            f"&code_challenge_method=S256"
            f"&redirect_to={urllib.parse.quote(redirect_with_pv)}"
        )

        # ---- 若在「註冊頁（新分頁）」就只顯示註冊表單 ----
        if qp.get("register") == "1":
            st.title(t("register_page_title"))
            st.markdown(f"### {t('register_header')}")
            with st.form("register_form", clear_on_submit=False):
                reg_email = st.text_input(t("reg_email"), key="reg_email")
                reg_pw = st.text_input(t("reg_pw"), type="password", key="reg_pw")
                reg_pw2 = st.text_input(t("reg_pw2"), type="password", key="reg_pw2")
                submit_reg = st.form_submit_button(t("btn_register"))
                if submit_reg:
                    import re as _re
                    if not _re.match(r"[^@]+@[^@]+\.[^@]+", reg_email or ""):
                        st.warning("Email 格式不正確。")
                    elif not reg_pw or len(reg_pw) < 6:
                        st.warning("密碼至少 6 個字元。")
                    elif reg_pw != reg_pw2:
                        st.warning("兩次輸入的密碼不一致。")
                    else:
                        try:
                            res = sb.auth.sign_up({"email": reg_email, "password": reg_pw})
                            session = getattr(res, "session", None)
                            user = getattr(res, "user", None)
                            if user and session:
                                token = session.access_token
                                _set_sb_auth_with_token(token)
                                st.session_state["user"] = _user_from_auth(user.model_dump(), token, provider="email")
                                st.success(f"註冊並登入成功：{st.session_state['user']['email']}")
                                st.rerun()
                            else:
                                st.info("註冊成功，請前往 Email 收信完成驗證後再登入。")
                        except Exception as e:
                            st.error(f"註冊失敗：{e}")

            # 回到登入（同分頁即可）
            st.markdown(
                f'<a href="{base_url}?lang={urllib.parse.quote(st.session_state["lang"])}" style="display:inline-block;margin-top:10px;">{t("back_to_login")}</a>',
                unsafe_allow_html=True
            )
            st.stop()  # 註冊頁不再往下渲染登入 UI

        # ---- 登入頁（預設）----
        st.title(t("login_title"))
        st.markdown(f"### {t('login_subtitle')}")

        # Email 登入
        with st.form("login_form", clear_on_submit=False):
            login_email = st.text_input(t("email"), key="login_email")
            login_pw = st.text_input(t("password"), type="password", key="login_pw")
            submit_login = st.form_submit_button(t("btn_login"))
            if submit_login:
                try:
                    res = sb.auth.sign_in_with_password({"email": login_email, "password": login_pw})
                    session = getattr(res, "session", None)
                    user = getattr(res, "user", None)
                    if not (session and user):
                        st.error("登入失敗，請檢查帳密或是否已完成信箱驗證。")
                    else:
                        token = session.access_token
                        _set_sb_auth_with_token(token)
                        st.session_state["user"] = _user_from_auth(user.model_dump(), token, provider="email")
                        st.success(f"登入成功：{st.session_state['user']['email']}")
                        st.rerun()
                except Exception as e:
                    st.error(f"登入失敗：{e}")

        # 同一行並排：「建立新帳號（開新分頁）」與「使用 Google 登入」
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f'''
                <a href="{register_url}" target="_blank"
                   style="display:inline-block;width:100%;text-align:center;padding:10px 14px;border-radius:8px;
                          border:1px solid #6b7280;background:#2b2f36;color:#fff;text-decoration:none;">
                   {t("btn_build_account")}
                </a>
                ''',
                unsafe_allow_html=True
            )
        with c2:
            st.markdown(
                f'''
                <a href="{google_login_url}"
                   style="display:inline-block;width:100%;text-align:center;padding:10px 14px;border-radius:8px;
                          border:1px solid #444;background:#1f6feb;color:#fff;text-decoration:none;">
                   {t("btn_google_login")}
                </a>
                ''',
                unsafe_allow_html=True
            )

        if require_login:
            st.stop()
        else:
            return None

    # C) 已登入 → 顯示狀態 + 登出
    st.info(t("current_login").format(
        name=st.session_state["user"]["full_name"], email=st.session_state["user"]["email"]
    ))
    if st.button(t("logout")):
        try:
            sb.auth.sign_out()
            sb.postgrest.auth(st.secrets["supabase"]["anon_key"])
        except Exception:
            pass
        for k in ["user","characters","image_base64","ocr_text","corrected_text",
                  "combined_prompt","prompt_template","prompt_input","translation",
                  "log_id","ocr_version","corrected_text_version", "pages", "main_image_url"]:
            st.session_state.pop(k, None)
        st.rerun()

# ✅ 啟用門神（未登入就無法操作）
# user = auth_gate(require_login=True)

# ===========================================
# 頁面標題
# ===========================================
st.title(t("app_title"))

# 🚩 這裡呼叫，之後所有 get_user_id() 都穩定
ensure_stable_user_id()

# st.caption(f"UID：{st.session_state.get('user_id')}｜來源：{st.session_state.get('_uid_src','?')}")

# ===========================================
# ========= 新增：多頁與 DB upsert 用 Helper =========
# ===========================================
def ensure_pages_list():
    """初始化 pages 陣列。每一頁是一個 dict：image_url/raw_bytes/ocr_text/corrected_text/output_text"""
    st.session_state.setdefault("pages", [])
    return st.session_state["pages"]

def reset_pages():
    for k in ["pages"]:
        st.session_state.pop(k, None)

def _page_ls_key(suffix: str, idx: int) -> str:
    return _ls_key(f"{suffix}_{idx}")

def upsert_translation_page(log_id: str, page_index: int, patch: dict):
    """
    將單頁欄位寫回 translation_pages（若不存在就插入；存在就更新）。
    需要你已有的唯一鍵：ON CONFLICT (log_id, page_index)
    """
    if not log_id:
        return
    patch = {k: v for k, v in patch.items() if v is not None}
    base = {"log_id": log_id, "page_index": page_index}
    payload = base | patch
    try:
        sb.table("translation_pages").upsert(
            payload, on_conflict="log_id,page_index"
        ).execute()
    except Exception as e:
        if SHOW_DEBUG:
            st.warning(f"translation_pages upsert 失敗：{e}")

def _get_or_create_log_for_pages() -> str | None:
    """
    多頁流程上傳時，先建立/沿用一筆草稿 log，允許 combined_prompt 為空。
    規則：沿用 user_id 最新的 draft；沒有就 insert 一筆只含 user_id 的草稿。
    """
    if st.session_state.get("log_id"):
        return st.session_state["log_id"]

    user_id = get_user_id()
    try:
        q = (sb.table("translation_logs")
              .select("id")
              .eq("user_id", user_id)
              .eq("status", "draft")
              .order("created_at", desc=True)
              .limit(1)
              .execute())
        if q.data:
            st.session_state["log_id"] = q.data[0]["id"]
            return st.session_state["log_id"]
    except Exception:
        pass

    try:
        res = (sb.table("translation_logs")
               .insert({"user_id": user_id, "status": "draft"})
               .execute())
        new_id = res.data[0]["id"]
        st.session_state["log_id"] = new_id
        return new_id
    except Exception as e:
        st.error(f"建立草稿失敗：{e}")
        return None

# ===========================================
# Sidebar（用固定 ID 做值，format_func 顯示 i18n 文案）
# ===========================================
st.sidebar.header(t("sidebar_header"))
menu = st.sidebar.radio(
    t("sidebar_choose"),
    ["ocr", "edit", "translate"],
    format_func=lambda x: {"ocr": t("menu_ocr"), "edit": t("menu_edit"), "translate": t("menu_translate")}[x]
)

temperature = st.sidebar.slider(
    t("temp_label"),
    min_value=0.0,
    max_value=1.0,
    value=0.95,
    step=0.05,
    help=t("temp_help")
)

# ===========================================
# Helper：取得當前使用者 ID / Email
# ===========================================
def get_user_id():
    # u = st.session_state.get("user") or {}
    # return u.get("id") or "guest"
    # return "00000000-0000-0000-0000-000000000000"
    return st.session_state.get("user_id") or ensure_stable_user_id()


def get_user_email():
    u = st.session_state.get("user") or {}
    return u.get("email") or ""

# 🔸新增：確保寫入/更新前一定用使用者 token（而不是 anon）
def _ensure_user_token():
    # u = st.session_state.get("user")
    # if not u:
    #     return
    # tok = u.get("access_token")
    # if tok:
    #     try:
    #         sb.postgrest.auth(tok)
    #     except Exception:
    #         pass
        return  # 登入關閉，永遠用 anon key


# ======================================================
# 🟢 ステップ1：登場人物登録（穩定版：用版本號重置 key）
# ======================================================
if menu == "ocr":
    st.subheader(t("char_section_title"))
    st.markdown(t("char_section_desc"))

    if "char_uploader_ver" not in st.session_state:
        st.session_state["char_uploader_ver"] = 0
    if "char_fields_ver" not in st.session_state:
        st.session_state["char_fields_ver"] = 0

    upload_key = f"char_img_{st.session_state['char_uploader_ver']}"
    name_key   = f"char_name_{st.session_state['char_fields_ver']}"
    desc_key   = f"char_desc_{st.session_state['char_fields_ver']}"

    char_img = st.file_uploader(t("char_img_uploader"), type=["jpg", "jpeg", "png"], key=upload_key)
    char_name = st.text_input(t("char_name"), key=name_key)
    char_desc = st.text_area(t("char_desc"), key=desc_key)

    if st.button(t("btn_char_add")):
        if char_img and char_name:
            img_bytes = char_img.read()

            # ⚠️ 新增：上傳角色圖到 Storage
            uid = get_user_id()
            import uuid as _uuid
            file_id = str(_uuid.uuid4())
            # 你也可以保留原始副檔名，這裡用 png 統一
            storage_path = _make_user_scoped_path(uid, f"characters/{file_id}.png")
            image_url = storage_upload_bytes(storage_path, img_bytes, content_type="image/png")

            # 👇 這行是偵錯輸出（角色圖）
            # st.write("character_image_url =", image_url)

            st.session_state["characters"] = st.session_state.get("characters", [])
            st.session_state["characters"].append({
                "image_bytes": img_bytes,
                "name": char_name,
                "image_url": image_url,
                "description": char_desc
            })
            st.success(f"已註冊角色：{char_name}" if st.session_state["lang"] == "zh-Hant" else f"已登记角色：{char_name}")
            st.session_state["char_uploader_ver"] += 1
            st.session_state["char_fields_ver"] += 1
            st.rerun()
        else:
            st.warning("圖片與名稱為必填欄位" if st.session_state["lang"] == "zh-Hant" else "图片与名称为必填栏位")

    if "characters" in st.session_state and st.session_state["characters"]:
        st.markdown(t("char_list_header"))
        for i, char in enumerate(st.session_state["characters"]):
            col1, col2, col3 = st.columns([0.3, 0.5, 0.2])

            with col1:
            # 角色縮圖：優先用 bytes（本地即時預覽），沒有再用 URL（跨回合/跨裝置）
                try:
                    img_bytes = char.get("image_bytes")
                    img_url   = char.get("image_url")

                    if isinstance(img_bytes, (bytes, bytearray)) and len(img_bytes) > 0:
                        st.image(Image.open(io.BytesIO(img_bytes)), caption=None, width=100)
                    elif isinstance(img_url, str) and img_url:
                        st.image(img_url, caption=None, width=100)
                    else:
                        st.write("（無圖片）" if st.session_state["lang"]=="zh-Hant" else "（无图片）")

                except Exception:
                    # 若 bytes 顯示失敗（格式或壞檔），改用 URL；再不行就顯示佔位文字
                    img_url = char.get("image_url")
                    if isinstance(img_url, str) and img_url:
                        st.image(img_url, caption=None, width=100)
                    else:
                        st.write("（無圖片）" if st.session_state["lang"]=="zh-Hant" else "（无图片）")


            with col2:
                new_name = st.text_input(f"{('名稱' if st.session_state['lang']=='zh-Hant' else '名称')}（{i}）", char["name"], key=f"edit_name_{i}")
                new_desc = st.text_area(f"{('性格／特徵' if st.session_state['lang']=='zh-Hant' else '性格／特征')}（{i}）", char["description"], key=f"edit_desc_{i}")
                if st.button(t("btn_update").format(name=char['name']), key=f"update_{i}"):
                    st.session_state["characters"][i]["name"] = new_name
                    st.session_state["characters"][i]["description"] = new_desc
                    st.success(f"已更新角色：{new_name}" if st.session_state["lang"] == "zh-Hant" else f"已更新角色：{new_name}")

            with col3:
                if st.button(t("btn_delete"), key=f"delete_{i}"):
                    deleted_name = st.session_state["characters"][i]["name"]
                    del st.session_state["characters"][i]
                    st.success(f"已刪除角色：{deleted_name}" if st.session_state["lang"] == "zh-Hant" else "已删除角色：{deleted_name}")
                    st.rerun()

    # -------------------------
    # ✅ 新增：多頁上傳 + 立即 upsert page 殼
    # -------------------------
    st.markdown("---")

    pages = ensure_pages_list()

    uploaded_files = st.file_uploader(
        t("main_img_uploader"),
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="multi_main_imgs"
    )

    # 限制一次最多 5 張
    if uploaded_files and len(uploaded_files) > 5:
        st.warning("一次最多選 5 張圖片。" if st.session_state["lang"]=="zh-Hant" else "一次最多选 5 张图片。")

    if uploaded_files:
        # 新上傳時，清掉舊的單頁狀態
        reset_pages()
        pages = ensure_pages_list()

        # 先確保有 log_id，好把 image_url 立即 upsert 進子表
        log_id = _get_or_create_log_for_pages()

        uid = get_user_id()
        import uuid as _uuid

        for i, f in enumerate(uploaded_files[:5]):
            # 轉 PNG bytes
            img = Image.open(f)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            raw_png_bytes = buf.getvalue()

            # 上傳 Storage：以 logs/<log_id>/pages/<i>.png
            if log_id:
                storage_path = _make_user_scoped_path(uid, f"logs/{log_id}/pages/{i}.png")
            else:
                storage_path = _make_user_scoped_path(uid, f"main/{str(_uuid.uuid4())}.png")

            image_url = storage_upload_bytes(storage_path, raw_png_bytes, content_type="image/png")

            # 存入 pages 陣列
            pages.append({
                "image_url": image_url,
                "raw_bytes": raw_png_bytes,
                "ocr_text": None,
                "corrected_text": None,
                "output_text": None
            })

            # 立即 upsert 到 translation_pages（只有 image_url 與頁序）
            if log_id and image_url:
                upsert_translation_page(log_id, i, {"image_url": image_url})

        st.success(("已上傳 {} 張頁面".format(len(pages)) if st.session_state["lang"]=="zh-Hant"
                    else "已上传 {} 张页面".format(len(pages))))

    # 頁面縮圖預覽
    if pages:
        try:
            st.image(
                [Image.open(io.BytesIO(p["raw_bytes"])) for p in pages if p.get("raw_bytes")],
                caption=[f"Page {i}" for i in range(len(pages))],
                use_container_width=True
            )
        except Exception:
            pass

    # 逐頁 OCR
    if pages and st.button(t("btn_run_ocr")):
        with st.spinner(("辨識中... 使用 GPT-4o 分析圖片" if st.session_state["lang"]=="zh-Hant" else "识别中... 使用 GPT-4o 分析图片")):
            # 準備角色名單
            character_context = "\n".join([
                f"・{c['name']}：{c['description']}"
                for c in st.session_state.get("characters", [])
            ]) or t("ocr_charlist_empty")

            prompt_text = t("ocr_system").format(charlist=character_context)

            log_id = _get_or_create_log_for_pages()
            prog = st.progress(0.0)
            total = len(pages)

            for i, pg in enumerate(pages):
                try:
                    img_b64 = base64.b64encode(pg["raw_bytes"]).decode("utf-8")
                    image_url = f"data:image/png;base64,{img_b64}"

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_text},
                            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
                        ]
                    )
                    ocr_text = (response.choices[0].message.content or "").strip()
                    pages[i]["ocr_text"] = ocr_text

                    # DB：把 ocr_text 寫回該頁
                    if log_id:
                        upsert_translation_page(log_id, i, {"ocr_text": ocr_text})

                except Exception as e:
                    st.warning(f"OCR 第 {i+1} 頁失敗：{e}")

                prog.progress((i+1)/total)

            st.success("OCR 完成" if st.session_state["lang"]=="zh-Hant" else "OCR 完成")

# ======================================================
# 🟡 ステップ2：テキスト修正（多頁 Tabs）
# ======================================================
elif menu == "edit":
    pages = st.session_state.get("pages", [])
    if not pages:
        st.warning("請先上傳圖片並執行辨識。" if st.session_state["lang"]=="zh-Hant" else "请先上传图片并执行识别。")
    else:
        st.subheader(t("edit_title"))

        tabs = st.tabs([f"第{i+1}頁" if st.session_state["lang"]=="zh-Hant" else f"第{i+1}页" for i in range(len(pages))])

        for i, (tab, pg) in enumerate(zip(tabs, pages)):
            with tab:
                col1, col2 = st.columns([1, 1.3])
                with col1:
                    st.markdown(t("orig_image"))
                    if pg.get("raw_bytes"):
                        st.image(Image.open(io.BytesIO(pg["raw_bytes"])), use_container_width=True)

                with col2:
                    st.markdown(t("corr_area"))
                    # 若 localStorage 有每頁草稿，可在此讀回（可選）
                    try:
                        cached = ls_get(_page_ls_key("corrected_text", i))
                    except Exception:
                        cached = None
                    default_text = (cached if isinstance(cached, str) and cached.strip() else
                                    (pg.get("corrected_text") or pg.get("ocr_text") or ""))
                    new_text = st.text_area(
                        t("corr_input_label"),
                        value=default_text,
                        height=300,
                        key=f"corr_input_{i}"
                    )
                    if st.button(t("btn_save_corr"), key=f"save_corr_{i}"):
                        pages[i]["corrected_text"] = new_text
                        # 寫回 localStorage（每頁一個 key）
                        try:
                            ls_set(_page_ls_key("corrected_text", i), new_text)
                        except Exception:
                            pass
                        # DB：更新 corrected_text
                        if st.session_state.get("log_id"):
                            upsert_translation_page(st.session_state["log_id"], i, {"corrected_text": new_text})
                        st.success(t("saved_corr"))

# ======================================================
# 🟣 ステップ3：輸入提示並翻譯（逐頁翻譯＋合併顯示）
# ======================================================
elif menu == "translate":
    # 若是多頁流程，先用各頁文字自動組一份「合併原文」供舊有模板使用
    pages = st.session_state.get("pages", [])
    if pages and "corrected_text" not in st.session_state:
        merged = []
        for i, pg in enumerate(pages):
            src = (pg.get("corrected_text") or pg.get("ocr_text") or "").strip()
            merged.append(f"【第{i+1}頁】\n{src}" if src else f"【第{i+1}頁】\n")
        st.session_state["corrected_text"] = "\n\n".join(merged)

    # 舊有邏輯：若沒有任何來源，才提示
    if not pages and "corrected_text" not in st.session_state:
        st.warning("請先完成文字修正步驟。" if st.session_state["lang"]=="zh-Hant" else "请先完成文字修正步骤。")
    else:
        st.subheader(t("translate_input_title"))

        # ---------- 工具函式（只定義，整合草稿／定稿邏輯） ----------
        def _get_combined() -> str:
            return (
                st.session_state.get("combined_prompt")
                or st.session_state.get("prompt_template")
                or st.session_state.get("prompt_input")
                or ""
            ).strip()

        def _create_log_only_here(sb_client, combined_text: str):
            """
            改為「草稿／定稿」邏輯：
            1) 若 session 內已有 log_id -> 直接沿用
            2) 若無 log_id -> 先嘗試在 DB 找 user_id 的 'draft'，有則沿用；無才 insert 新草稿
            新草稿僅在沒有現存草稿時才會 insert
            """
            if st.session_state.get("log_id"):
                return st.session_state.get("log_id")
            if not combined_text:
                return None

            _ensure_user_token()

            user_id = get_user_id()

            # 先找是否已有草稿
            try:
                q = (
                    sb_client.table("translation_logs")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("status", "draft")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if q.data:
                    draft_id = q.data[0]["id"]
                    st.session_state["log_id"] = draft_id
                    return draft_id
            except Exception:
                # 找不到草稿時就走 insert
                pass

            # 沒有草稿 -> 建立新草稿
            payload = {
                "user_id": user_id,
                "combined_prompt": combined_text,
                "output_text": None,
                "status": "draft",
            }

            # ✅ 新增：主圖 URL（如你還有沿用）
            main_image_url = st.session_state.get("main_image_url")
            if main_image_url:
                payload["image_url"] = main_image_url   # 對應 DB 欄位：image_url (text)

            # # ✅ 角色資料（若 DB 有 character_data: jsonb）
            chars = st.session_state.get("characters")
            if chars:
                try:
                    payload["character_data"] = [
                        {
                            "name": c.get("name"),
                            "description": c.get("description"),
                            "image_url": c.get("image_url") or None,
                        }
                        for c in chars
                    ]
                except Exception:
                    pass

            # 可選：把目前可得的上下文也一併帶進草稿（若資料表已有對應欄位）
            ocr_text = st.session_state.get("ocr_text")
            if ocr_text is not None:
                payload["ocr_text"] = ocr_text
            corrected_text = st.session_state.get("corrected_text")
            if corrected_text is not None:
                payload["corrected_text"] = corrected_text

            res = (
                sb_client.table("translation_logs")
                .insert(payload)
                .execute()
            )
            new_id = res.data[0]["id"]
            st.session_state["log_id"] = new_id
            st.toast("💾 已建立草稿（等待譯文）" if st.session_state["lang"]=="zh-Hant" else "💾 已建立草稿（等待译文）", icon="💾")
            return new_id

        def _update_prompt_if_possible(sb_client):
            """
            若有草稿 log_id -> 更新該筆的 combined_prompt（以及可選同步的 ocr/corrected/character_data）
            """
            log_id = st.session_state.get("log_id")
            combined = _get_combined()
            if not (log_id and combined):
                return False
            _ensure_user_token()

            update_dict = {"combined_prompt": combined}

            # ✅ 同步主圖 URL（若有）
            main_image_url = st.session_state.get("main_image_url")
            if main_image_url:
                update_dict["image_url"] = main_image_url

            # ✅ 同步 OCR/修正文（若有）
            ocr_text = st.session_state.get("ocr_text")
            if ocr_text is not None:
                update_dict["ocr_text"] = ocr_text
            corrected_text = st.session_state.get("corrected_text")
            if corrected_text is not None:
                update_dict["corrected_text"] = corrected_text

            # ✅ 同步角色資料（含 image_url）
            chars = st.session_state.get("characters")
            if chars:
                try:
                    update_dict["character_data"] = [
                        {
                            "name": c.get("name"),
                            "description": c.get("description"),
                            "image_url": c.get("image_url") or None,
                        }
                        for c in chars
                    ]
                except Exception:
                    pass

            sb_client.table("translation_logs").update(update_dict).eq("id", log_id).execute()
            return True

        def _update_output_if_possible(sb_client):
            """
            生成譯文後：
            1) 把 output_text 寫回草稿
            2) 將該筆標記為 finalized（並寫 finalized_at）
            3) 清掉 session 的 log_id，避免後續誤用
            """
            log_id = st.session_state.get("log_id")
            output = (st.session_state.get("translation") or "").strip()
            if not (log_id and output):
                return False
            _ensure_user_token()

            from datetime import datetime, timezone
            finalized_at = datetime.now(timezone.utc).isoformat()

            sb_client.table("translation_logs").update(
                {
                    "output_text": output,
                    "status": "finalized",
                    "finalized_at": finalized_at,
                }
            ).eq("id", log_id).execute()

            # 這一步很重要：定稿後結束草稿狀態
            st.session_state.pop("log_id", None)
            return True
        # ---------- 工具函式結束 ----------

        st.markdown(f"### {t('bg_title')}")
        st.caption(t("bg_caption"))
        bind_textarea_with_ls(
            key="background_style",
            label="輸入內容：" if st.session_state["lang"]=="zh-Hant" else "输入内容：",
            default_value=STRINGS[st.session_state["lang"]]["tpl_background"],
            height=200
        )

        if "characters" in st.session_state and st.session_state["characters"]:
            st.markdown(f"### {t('char_traits_title')}")
            st.caption(t("char_traits_caption"))

            # 只注入一次小字樣式（當提示標籤用）
            if not st.session_state.get("_char_hint_css"):
                st.markdown("""
                <style>
                .char-hint { font-size: 0.95rem; opacity: 0.85; margin: 6px 0 4px 0; }
                </style>
                """, unsafe_allow_html=True)
                st.session_state["_char_hint_css"] = True

            # 角色補充：一直展開
            valid_trait_keys = set()
            for idx, c in enumerate(st.session_state["characters"]):
                char_key = f"character_traits_{idx}"
                valid_trait_keys.add(char_key)

                if char_key not in st.session_state:
                    st.session_state[char_key] = STRINGS[st.session_state["lang"]]["tpl_character"]

                name = c.get("name", '角色' if st.session_state["lang"] == "zh-Hant" else '角色')
                hint = (f"🧑‍🎨 {name} 的角色補充（點此展開）"
                        if st.session_state["lang"] == "zh-Hant"
                        else f"🧑‍🎨 {name} 的角色补充（点此展开）")
                st.markdown(f"<div class='char-hint'>{hint}</div>", unsafe_allow_html=True)

                bind_textarea_with_ls(
                    key=char_key,
                    label="輸入內容：" if st.session_state["lang"]=="zh-Hant" else "输入内容：",
                    default_value=STRINGS[st.session_state["lang"]]["tpl_character"],
                    height=200
                )

                st.divider()

            # 清理不存在的角色輸入 key（含同步清掉 localStorage）
            for k in list(st.session_state.keys()):
                if k.startswith("character_traits_") and k not in valid_trait_keys:
                    try:
                        ls_remove(_ls_key(k))  # ← 同步移除瀏覽器 localStorage 的舊值
                    except Exception:
                        pass
                    del st.session_state[k]

        # ===== 這裡開始已經離開清理迴圈（很重要！）=====

        # 術語
        st.markdown(f"### {t('term_title')}")
        st.caption(t("term_caption"))
        bind_textarea_with_ls(
            key="terminology",
            label="輸入內容：" if st.session_state["lang"]=="zh-Hant" else "输入内容：",
            default_value=STRINGS[st.session_state["lang"]]["tpl_terminology"],
            height=200
        )

        # 翻譯方針
        st.markdown(f"### {t('policy_title')}")
        st.caption(t("policy_caption"))
        bind_textarea_with_ls(
            key="translation_policy",
            label="輸入內容：" if st.session_state["lang"]=="zh-Hant" else "输入内容：",
            default_value=STRINGS[st.session_state["lang"]]["tpl_policy"],
            height=200
        )

        # ===== 產生提示內容（唯一可建新 ID 的地方） =====
        if st.button(t("btn_save_and_build")):
            # 角色別補充段落
            per_char_sections = ""
            if "characters" in st.session_state and st.session_state["characters"]:
                blocks = []
                for idx, c in enumerate(st.session_state["characters"]):
                    char_key = f"character_traits_{idx}"
                    content = st.session_state.get(char_key, "").strip()
                    blocks.append(STRINGS[st.session_state["lang"]]["charblock"].format(
                        name=c.get('name','角色'), content=(content if content else ('（未填寫）' if st.session_state["lang"]=="zh-Hant" else '（未填写）'))
                    ))
                per_char_sections = "\n".join(blocks)

            # 若是多頁流程，st.session_state["corrected_text"] 已在上面自動合併生成
            combined_prompt = (
                STRINGS[st.session_state["lang"]]["combined_header"] + "\n\n" +
                STRINGS[st.session_state["lang"]]["sec_background"].format(content=st.session_state["background_style"]) +
                STRINGS[st.session_state["lang"]]["sec_terminology"].format(content=st.session_state["terminology"]) +
                STRINGS[st.session_state["lang"]]["sec_policy"].format(content=st.session_state["translation_policy"])
            )
            if per_char_sections:
                combined_prompt += STRINGS[st.session_state["lang"]]["sec_charblocks_title"] + per_char_sections + "\n\n"
            combined_prompt += STRINGS[st.session_state["lang"]]["sec_source"].format(source=st.session_state.get("corrected_text",""))

            st.session_state["combined_prompt"] = combined_prompt
            st.session_state["prompt_input"] = combined_prompt
            st.success("內容已儲存並整合。" if st.session_state["lang"]=="zh-Hant" else "内容已保存并整合。")

            try:
                # 取得目前組合好的提示內容（combined_prompt）
                combined_now = combined_prompt.strip()

                # 若提示內容是空的，顯示提示訊息
                if not combined_now:
                    st.info(
                        "⚠️ 尚未建立資料列；請先輸入提示內容。"
                        if st.session_state["lang"] == "zh-Hant"
                        else "⚠️ 尚未建立资料列；请先输入提示内容。"
                    )
                else:
                    # 🧩 交由函式自動判斷：沿用現有草稿或建立新的草稿
                    draft_id = _create_log_only_here(sb, combined_now)

                    # 📥 成功建立或沿用草稿後，把目前的提示內容寫入資料庫（冪等更新）
                    if draft_id and _update_prompt_if_possible(sb):
                        st.toast(
                            "✅ 已更新提示內容（同一筆）"
                            if st.session_state["lang"] == "zh-Hant"
                            else "✅ 已更新提示内容（同一笔）",
                            icon="💾"
                        )
                    else:
                        st.info(
                            "⚠️ 未能更新提示內容，請稍後再試。"
                            if st.session_state["lang"] == "zh-Hant"
                            else "⚠️ 未能更新提示内容，请稍后再试。"
                        )

            except Exception as e:
                st.error(
                    f"❌ 建立或更新輸入紀錄失敗：{e}"
                    if st.session_state["lang"] == "zh-Hant"
                    else f"❌ 建立或更新输入纪录失败：{e}"
                )

        st.subheader(t("custom_prompt_title"))
        bind_textarea_with_ls(
            key="prompt_input",
            label=t("custom_prompt_input"),
            default_value=st.session_state.get("prompt_input",""),
            height=300
        )

        if st.button(t("btn_save_prompt")):
            st.session_state["prompt_template"] = st.session_state["prompt_input"]
            st.success("提示內容已儲存" if st.session_state["lang"]=="zh-Hant" else "提示内容已保存")
            try:
                # 取得目前可用的提示內容（依序取 combined_prompt / prompt_template / prompt_input）
                combined_now = _get_combined().strip()

                if not combined_now:
                    st.info(
                        "⚠️ 尚未建立資料列；請先輸入提示內容。"
                        if st.session_state["lang"] == "zh-Hant"
                        else "⚠️ 尚未建立资料列；请先输入提示内容。"
                    )
                else:
                    draft_id = _create_log_only_here(sb, combined_now)
                    if draft_id and _update_prompt_if_possible(sb):
                        st.toast(
                            "✅ 已更新提示內容（同一筆）"
                            if st.session_state["lang"] == "zh-Hant"
                            else "✅ 已更新提示内容（同一笔）",
                            icon="💾"
                        )
                    else:
                        st.info(
                            "⚠️ 未能更新提示內容，請稍後再試。"
                            if st.session_state["lang"] == "zh-Hant"
                            else "⚠️ 未能更新提示内容，请稍后再试。"
                        )

            except Exception as e:
                st.error(
                    f"❌ 更新提示內容失敗：{e}"
                    if st.session_state["lang"] == "zh-Hant"
                    else f"❌ 更新提示内容失败：{e}"
                )

        # ===== 逐頁翻譯（新） =====
        if st.button(t("btn_run_translate")):
            prompt_for_translation = (
                st.session_state.get("prompt_template")
                or st.session_state.get("combined_prompt")
                or st.session_state.get("prompt_input")
            )
            if not prompt_for_translation:
                st.warning("請先產生或儲存提示內容，再執行翻譯。" if st.session_state["lang"]=="zh-Hant" else "请先生成或保存提示内容，再执行翻译。")
            else:
                with st.spinner("翻譯中... 使用 GPT-4o" if st.session_state["lang"]=="zh-Hant" else "翻译中... 使用 GPT-4o"):
                    log_id = _get_or_create_log_for_pages()
                    # 冪等更新一次主要 prompt（跟既有流程一致）
                    try:
                        _update_prompt_if_possible(sb)
                    except Exception as e:
                        if SHOW_DEBUG:
                            st.warning(f"更新主提示失敗：{e}")

                    pages = st.session_state.get("pages", [])
                    if not pages:
                        # 若不是多頁流程，維持舊單份翻譯（向下相容）
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages = [
                                    { "role": "system", "content": STRINGS[st.session_state["lang"]]["translate_system"] },
                                    {"role": "user", "content": prompt_for_translation}
                                ],
                                temperature=temperature,
                                top_p=0.95,
                            )
                            st.session_state["translation"] = response.choices[0].message.content.strip()
                        except Exception as e:
                            st.error((f"翻譯失敗：{e}" if st.session_state["lang"]=="zh-Hant" else f"翻译失败：{e}"))
                            st.session_state.pop("translation", None)
                    else:
                        prog = st.progress(0.0)
                        total = len(pages)
                        out_all = []

                        for i, pg in enumerate(pages):
                            src = (pg.get("corrected_text") or pg.get("ocr_text") or "").strip()
                            if not src:
                                pages[i]["output_text"] = ""
                                if log_id:
                                    upsert_translation_page(log_id, i, {"output_text": ""})
                                prog.progress((i+1)/total)
                                continue
                            try:
                                response = client.chat.completions.create(
                                    model="gpt-4o",
                                    messages=[
                                        {"role": "system", "content": STRINGS[st.session_state["lang"]]["translate_system"]},
                                        {"role": "user", "content": prompt_for_translation},
                                        {"role": "user", "content": f"【原始對白（第{i+1}頁）】\n{src}"}
                                    ],
                                    temperature=temperature,
                                    top_p=0.95,
                                )
                                out = (response.choices[0].message.content or "").strip()
                                pages[i]["output_text"] = out
                                out_all.append(f"【第{i+1}頁】\n{out}")
                                if log_id:
                                    upsert_translation_page(log_id, i, {"output_text": out})
                            except Exception as e:
                                st.error((f"翻譯第 {i+1} 頁失敗：{e}" if st.session_state["lang"]=="zh-Hant" else f"翻译第 {i+1} 页失败：{e}"))
                                pages[i]["output_text"] = ""
                            prog.progress((i+1)/total)

                        final_all = "\n\n".join(out_all).strip()
                        st.session_state["translation"] = final_all or st.session_state.get("translation")

                        if log_id and final_all:
                            try:
                                sb.table("translation_logs").update(
                                    {"output_text": final_all}
                                ).eq("id", log_id).execute()
                            except Exception as e:
                                if SHOW_DEBUG:
                                    st.warning(f"更新 translation_logs.output_text 失敗：{e}")

                # 舊有定稿寫回（保留）
                try:
                    if st.session_state.get("log_id"):
                        if _update_output_if_possible(sb):
                            st.toast("✅ 已儲存譯文到同一筆紀錄" if st.session_state["lang"]=="zh-Hant" else "✅ 已保存译文到同一笔纪录", icon="💾")
                        else:
                            st.toast("⚠️ 沒拿到譯文或缺少內容，已跳過儲存。" if st.session_state["lang"]=="zh-Hant" else "⚠️ 没拿到译文或缺少内容，已跳过保存。", icon="⚠️")
                    else:
                        st.info("已產生譯文，但尚未建立資料列；請先按「儲存並產生提示內容」。" if st.session_state["lang"]=="zh-Hant" else "已产生译文，但尚未建立资料列；请先按“保存并生成提示内容”。")
                except Exception as e:
                    st.error((f"儲存譯文失敗：{e}" if st.session_state["lang"]=="zh-Hant" else f"保存译文失败：{e}"))

        if "translation" in st.session_state:
            st.text_area(t("translate_result"), st.session_state["translation"], height=300)
