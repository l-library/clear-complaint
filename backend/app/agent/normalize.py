"""确定性归一化：把口语主诉折成可比对的书面表述。

模型不参与这一步。红旗规则要跑在这上面，如果归一化本身用模型，红旗就间接咨询了
模型，「红旗绝不咨询模型」这条非协商项当场失守。

归一化只做三件可解释的事：字符层面统一（全半角、大小写、空白）、常见错别字与拼音
替换、口语词到临床词的短语替换。所有替换表都在本模块里，改一个字都能看 diff。
"""

from __future__ import annotations

import re
import unicodedata

# 拼音与错别字：口语变体里出现，替换后与书面词同形。
#
# 两点教训：一是必须按长度从长到短替换，否则 "ke" 会把 "keng" 吃成「咳ng」；
# 二是含义不唯一的音节只能按词组替换（"gou" 可以是够也可以是狗，"li" 可以是厉
# 也可以是里），单字替换会把别的词改坏。
PINYIN_MAP: tuple[tuple[str, str], ...] = (
    ("睡gou", "睡够"),
    ("被gou", "被狗"),
    ("beima", "被马"),
    ("jiangya", "降压"),
    ("不shu服", "不舒服"),
    ("嘴chun", "嘴唇"),
    ("心huang", "心慌"),
    ("两条tui", "两条腿"),
    ("一个keng", "一个坑"),
    ("小水pao", "小水疱"),
    ("水pao", "水疱"),
    ("shou上", "手上"),
    ("jiao上", "脚上"),
    ("xiao时", "小时"),
    ("xiao腿", "小腿"),
    ("头yun", "头晕"),
    ("想shui", "想睡"),
    ("分zhong", "分钟"),
    ("容易lei", "容易累"),
    ("总觉得lei", "总觉得累"),
    ("总lei", "总累"),
    ("tiao得", "跳得"),
    ("laduzi", "拉肚子"),
    ("四五ci", "四五次"),
    ("红zhen子", "红疹子"),
    ("xiong口", "胸口"),
    ("二十fen钟", "二十分钟"),
    ("点xue", "点血"),
    ("又teng", "又疼"),
    ("红dian", "红点"),
    ("shen上", "身上"),
    ("不太yang", "不太痒"),
    ("di热", "低热"),
    ("fa烧", "发烧"),
    ("fa热", "发热"),
    ("hen少", "很少"),
    ("li害", "厉害"),
    ("zhe了", "蜇了"),
    ("chuan得", "喘得"),
    ("tong", "痛"),
    ("tou", "头"),
    ("du", "肚"),
    ("shao", "烧"),
    ("liu", "流"),
    ("sang", "嗓"),
    ("zi", "子"),
)

# 口语词到临床词。左边是患者会说的，右边是文件里会写的。
# 顺序有意义：长短语先替换，否则「拉肚子」会被「肚子」先吃掉。
COLLOQUIAL_MAP: tuple[tuple[str, str], ...] = (
    ("拉肚子", "腹泻"),
    ("胸口压得慌", "胸部压榨性疼痛"),
    ("胸口闷", "胸闷"),
    ("心口疼", "胸痛"),
    ("胸口痛", "胸痛"),
    ("胸口发闷", "胸闷"),
    ("胸口疼", "胸痛"),
    ("喘不上气", "呼吸困难"),
    ("上不来气", "呼吸困难"),
    ("憋得慌", "呼吸困难"),
    ("脑壳", "头"),
    ("嗓子疼", "咽痛"),
    ("嗓子痛", "咽痛"),
    ("喉咙痛", "咽痛"),
    ("流鼻涕", "流涕"),
    ("鼻涕", "流涕"),
    ("发烧", "发热"),
    ("烧得厉害", "高热"),
    ("出冷汗", "冷汗"),
    ("浑身没劲", "乏力"),
    ("没力气", "乏力"),
    ("想吐", "恶心"),
    ("肚子疼", "腹痛"),
    ("肚子痛", "腹痛"),
    ("肚子", "腹"),
    ("拉稀", "腹泻"),
    ("嗓子", "咽部"),
    # 慢性病与体征的口语叫法：患者说左边，指南写右边。族实验的画像与主诉都用得到
    ("慢阻肺", "慢性阻塞性肺疾病（COPD）"),
    ("腿有点肿", "下肢水肿"),
    ("腿肿", "下肢水肿"),
    ("容易累", "疲乏"),
    ("水泡", "水疱"),
)

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[，。、；：！？,.;:!?\u3000]")


def fold_chars(text: str) -> str:
    """只做字符层面的统一：全半角、大小写、空白、标点。

    引用核验用这一层。它不改任何实词，所以「逐字」仍然是逐字——把「发烧」折成
    「发热」的那种放宽只属于红旗与检索，不属于引文比对。
    """
    folded = unicodedata.normalize("NFKC", text).lower()
    return _PUNCTUATION.sub("", _WHITESPACE.sub("", folded))


def normalize(text: str) -> str:
    """口语归一化：字符统一之后再折错别字与口语词。红旗与检索用这一层。"""
    folded = fold_chars(text)
    for wrong, right in sorted(PINYIN_MAP, key=lambda pair: -len(pair[0])):
        folded = folded.replace(wrong, right)
    for colloquial, clinical in COLLOQUIAL_MAP:
        folded = folded.replace(colloquial, clinical)
    return folded


# 自我归因：用户把自己的判断掺进主诉。「我好像感冒了」里的「感冒了」不是症状，
# 是一个未经验证的结论。输入侧干预把这段摘出来单独存字段，不进入推理链。
_ATTRIBUTION = re.compile(
    r"(?:我|自己)?(?:好像|似乎|估计|感觉|觉得|应该|可能|大概|怕是)"
    r"(?:是|得了|得了|患了|患上)?([^，。,.！!？?；;]{1,10})"
)


def split_attribution(text: str, known_terms: set[str]) -> tuple[str, str | None]:
    """把自我归因摘出主诉，返回（剩余主诉，归因）。

    known_terms 是受控词表里的病名与口语别名。只有落在词表里的才算归因——否则
    「我觉得很冷」会被误摘成结论，「冷」不是病名。
    """
    for match in _ATTRIBUTION.finditer(text):
        phrase = match.group(0)
        candidate = match.group(1)
        for term in sorted(known_terms, key=len, reverse=True):
            if term and term in candidate:
                remainder = (text[: match.start()] + text[match.end() :]).strip(" ，,。.；;")
                return remainder, term
        del phrase
    return text, None
