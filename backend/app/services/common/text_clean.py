"""PDF 提取文本的通用清洗（知识库摄入、题库导入共用）

PDF 提出来的文本有两个通病，肉眼都看不出来：

1. **字是「部首变体」**：⽤(U+2F64) 而不是常用字 用(U+7528)。看着一模一样、
   码位不同——分词会失效、关键词精确匹配必然落空。
2. **换行是「排版换行」**：一行只排 30 来字就换行，那不是句子边界；
   直接拿去切块/切题，句子会被从中间劈开。

两条规则都**只对 PDF 用**：markdown 的换行是语法（标题/列表），不能拼。
"""
import re
import unicodedata

# 康熙部首区（2F00-2FDF）和兼容汉字区（F900-FAFF）NFKC 能自动还原；
# 「部首补充区」（2E80-2EFF）NFKC 管不了，按实际语料显式映射（照数据补，不追求完备）。
# 加新字的方法：扫一遍原始文本里落在 2E80-2FDF / F900-FAFF 的字符，
# 挑出 NFKC 修不掉的那些，按名字里的读音对到常用字。
_RADICAL_SUPPLEMENT = {
    "⺓": "幺", "⺟": "母", "⻁": "虎", "⻅": "见", "⻆": "角", "⻉": "贝",
    "⻋": "车", "⻓": "长", "⻔": "门", "⻚": "页", "⻛": "风", "⻜": "飞",
    "⻢": "马", "⻣": "骨", "⻬": "齐", "⻥": "鱼",
}


def normalize_variants(text: str) -> str:
    """变体字还原成常用字（⽤→用、⻓→长）

    注意只动「部首/兼容区」，不做全量 NFKC——那会顺手把中文全角标点
    （，：（）？）改成半角，正文面貌就变了。
    """
    out = []
    for ch in text:
        cp = ord(ch)
        if 0x2F00 <= cp <= 0x2FDF or 0xF900 <= cp <= 0xFAFF:
            out.append(unicodedata.normalize("NFKC", ch))
        else:
            out.append(_RADICAL_SUPPLEMENT.get(ch, ch))
    return "".join(out)


_SENTENCE_END = "。！？!?：；;"                                  # 行尾是这些 = 上句已说完（; 管 PDF 里的代码行）
_ITEM_HEAD = re.compile(r"^(\d+[）).、]|[①-⑩]|[-•*·])")        # 列表项/编号条目的开头


def is_question_line(line: str) -> bool:
    """题面判据（照问答型语料的数据定的，不是通用真理）

    - 以问号结尾、4~150 字：题面都是完整的一问
    - 排除「答：」「答案」「【」开头：答案里的自问句/举例（"【doc1】…问题：…？"）不是新题
    - 行内不能夹着句号/叹号：题面是"纯问题"（"什么是 Python？为什么流行？"），
      而答案里的举例是一整段话（"…修正。这个过程就像自问自答：我做了什么？…"）。
      注意**不能**按问号个数排除——"…有哪些？有什么区别？"就是一道真题。
    注意也**不能**按"数字编号开头"排除：答案尾行和题干粘一起时，题面会带上编号前缀。
    """
    s = line.strip()
    if not s.endswith(("？", "?")) or not (4 <= len(s) <= 150):
        return False
    if s.startswith(("答：", "答案", "【")):
        return False
    return "。" not in s and "！" not in s


def join_wrapped_lines(text: str) -> str:
    """把 PDF 的「排版换行」拼回句子

    PDF 一行只排 30 来字就换行，换行处多半不是句子结束——
    直接喂给切分器，它会把排版换行当语义边界，把句子从中间劈开。
    """
    out: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            out.append("")                     # 空行 = 段落边界，保留
            continue
        # 上一行没说完 + 这行不是新条目 + 这行本身不是一道完整题面 → 拼回去。
        # 最后一条必不可少：答案尾行（如"4）有序：list、tuple…（3.7+）"）没带句号时，
        # 会把下一道题粘上来，连题带答案一起被误判（踩过）。
        if (out and out[-1] and out[-1][-1] not in _SENTENCE_END
                and not _ITEM_HEAD.match(s) and not is_question_line(s)):
            prev = out[-1]
            glue = " " if (prev[-1].isascii() and prev[-1].isalnum() and s[0].isascii() and s[0].isalnum()) else ""
            out[-1] = prev + glue + s
        else:
            out.append(s)
    return "\n".join(out)


def clean_pdf_text(text: str) -> str:
    """PDF 文本清洗 = 变体字还原 → 排版换行拼回句子

    （题边界、章节结构不在这里管：那是各消费方自己的切分策略）
    """
    return join_wrapped_lines(normalize_variants(text))
