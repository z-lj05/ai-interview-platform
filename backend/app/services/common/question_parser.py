"""题库导入的「切题器」：把上传的文件切成题目列表

一次文件导入要经过三道工序，只有第一道分文档类型：

    提文本（pdfplumber / 直接读字节）→ 清洗（text_clean）→ ★切题（本模块）

★ 是最容易失效的一道：切题规则是**照语料长相定的**，不是通用真理——
换个排版的 PDF 就可能切错（09-13 切知识库时，想当然的排除规则吃掉过 3 道真题）。
所以规则只留一份、住在公共模块里：管理端页面和命令行脚本都调它。
（之前 import_pdf_questions.py 里就留着一份旧拷贝：题面长度还是 80、没排除「【」，
 这就是"一处实现"没做彻底的长相——改规则时漏掉的那一方不会报错，只会默默切错。）

两种已知的文档长相：
- **问句式**：题面 = 一个以问号结尾的短行，其后到下一个问号行之间的都是答案
  （PDF 提取出来的文本只能按这个认；docx 没用标题样式时也落这条）
- **结构化**：题面 = "### " 标题行，章节 = "## " 标题行
  （markdown 原生就有；docx 的「标题 1/2/3」样式会在提取时译成同样的标记）
"""
import io
import logging
import re

import pdfplumber
from docx import Document

from app.services.common.text_clean import clean_pdf_text, is_question_line, normalize_variants

# pdfminer 对某些 PDF 会刷 FontBBox 警告，静音处理（不影响提取结果）
logging.getLogger("pdfminer").setLevel(logging.ERROR)

PDF_EXTENSIONS = {"pdf"}
MD_EXTENSIONS = {"md", "markdown"}
DOCX_EXTENSIONS = {"docx"}
TEXT_EXTENSIONS = {"txt"}
ALLOWED_EXTENSIONS = PDF_EXTENSIONS | MD_EXTENSIONS | DOCX_EXTENSIONS | TEXT_EXTENSIONS


# ── 切题策略 ────────────────────────────────────────────────────────────


def split_qa_pairs_pdf(text: str) -> list[dict]:
    """问句式切题：题面 = 以问号结尾的短行，其后到下一个问号行之间是答案

    判据不写在这里——调 text_clean.is_question_line（全项目唯一权威）。
    第一道题之前的内容（封面、推广）自动丢弃：还没开题时的行没人收。
    """
    pairs: list[dict] = []
    current_q: str | None = None          # 当前题面（None = 还没遇到第一道题）
    answer_lines: list[str] = []

    for line in text.split("\n"):
        s = line.strip()
        if is_question_line(s):
            if current_q is not None:     # 遇到新题面 → 上一题在这里收尾
                pairs.append({
                    "question": current_q,
                    "reference_answer": "\n".join(answer_lines).strip(),
                })
            current_q = s
            answer_lines = []
        elif current_q is not None:
            answer_lines.append(s)

    if current_q is not None:             # 扫完了，收尾最后一题
        pairs.append({
            "question": current_q,
            "reference_answer": "\n".join(answer_lines).strip(),
        })
    return pairs


def split_qa_pairs_md(text: str) -> list[dict]:
    """结构化 MD 切题：边界直接写在文件里（"### " 开题 / "## " 开章节），不用猜

    章节名记进 chapter，后面 build_items 会把它落到 tags——
    这样管理端按标签就能筛出"项目整体""RAG"这种按章分组的题。
    """
    pairs: list[dict] = []
    chapter = ""
    current_q: str | None = None
    answer_lines: list[str] = []

    def flush():
        if current_q is not None:
            pairs.append({
                "chapter": chapter,
                "question": current_q,
                "reference_answer": "\n".join(answer_lines).strip(),
            })

    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("### "):
            flush()
            current_q = re.sub(r"^Q\d+[：:]\s*", "", s[4:].strip())   # "Q1：xx" → "xx"
            answer_lines = []
        elif s.startswith("## "):
            flush()
            current_q = None                                          # 章节标题本身不是题
            answer_lines = []
            chapter = re.sub(r"^\d+\.\s*", "", s[3:].strip())         # "1. 项目整体" → "项目整体"
        elif current_q is not None:
            if s == "---":                                            # 分隔线不算答案
                continue
            answer_lines.append(line)

    flush()
    return pairs


# ── 文件入口 ────────────────────────────────────────────────────────────


def _extract_pdf_text(file_bytes: bytes) -> str:
    """PDF 字节 → 清洗后的全文文本

    清洗做两件事（见 text_clean）：变体字还原（⽤→用）+ 排版换行拼回句子。
    不做的话，题干里存的是康熙部首，分词和关键词精确匹配会一直失效。

    注意：pdfplumber 是**同步阻塞**接口，没有异步版。调用方负责把它丢到线程池，
    否则一个几十页的 PDF 会把整个事件循环堵住（所有请求一起等它读完）。
    """
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        raw = "\n".join(page.extract_text() or "" for page in pdf.pages)
    # 网页转 PDF 的遗留：一部分换行存成了"反斜杠+n"两个字符，先还原成真换行
    return clean_pdf_text(raw.replace("\\n", "\n"))


def _heading_level(style_name: str) -> int:
    """「Heading 2」/「标题 2」→ 2；认不出级别就当 1（最粗的章节级）"""
    m = re.search(r"(\d+)", style_name or "")
    return int(m.group(1)) if m else 1


def _extract_docx_text(file_bytes: bytes) -> str:
    """docx 字节 → 文本（**把 Word 的标题样式翻译成 markdown 的 # 标记**）

    Word 的「标题 1/2/3」是**结构化数据**，和 markdown 的 `#` 一样明确——
    但 python-docx 取出来只剩纯文字，样式信息藏在 p.style.name 里。
    我们把它译回 "## " / "### "，MD 切题器就能直接吃：
    "标题 = 一道题"的结构在 docx 里同样成立。

    映射用**相对级别**，不用绝对级别（踩过：第一版写死"1、2 级 = 章节"，
    结果一份"标题 1 当章节、标题 2 当题目"的正常文档只切出 1 道题——
    两道题目被当成章节名吃掉了）。不同人写 Word 的习惯差很多：
    有人标题 1 当章节，也有人标题 1 直接就是题目，绝对级别没有含义。
    所以：**用得最浅的那级标题当章节**，比它深的一律当题面；
    只有一级标题的文档（全是题目、没有章节）→ 全当题面。

    没用标题样式的文档（很多人只是把字加粗）→ 译出来一个 # 都没有，
    MD 切题器切出 0 题，自动落到问句式（见 _best_effort_split 的兜底）。

    已知不支持：**表格里的文字**（doc.paragraphs 取不到，Word 表格问答常见）。
    """
    doc = Document(io.BytesIO(file_bytes))

    paras: list[tuple[int, str]] = []      # (标题级别, 文本)；0 = 正文段落
    levels: set[int] = set()
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name or ""
        is_heading = style.lower().startswith("heading") or style.startswith("标题")
        level = _heading_level(style) if is_heading else 0
        if is_heading:
            levels.add(level)
        paras.append((level, text))

    chapter_level = min(levels) if len(levels) > 1 else None

    out: list[str] = []
    for level, text in paras:
        if level == 0:
            out.append(text)
        elif chapter_level is not None and level == chapter_level:
            out.append(f"## {text}")
        else:
            out.append(f"### {text}")
    return normalize_variants("\n".join(out))


def _best_effort_split(text: str) -> dict:
    """两套切题规则都跑——**但结构标记出现时，以结构为准，不猜**

    判据只看 "### "（题面级标记）：它一出现，说明文档自己划好了题边界，
    比"按问号猜"可靠，不该让猜的那套赢。
    （踩过：一份标题式文档里题目恰好都以"？"结尾，两套切法数量打平，
     按"谁切得多用谁"落到了问句式——而问句式不认识 "### " 标记，
     于是题面里**带着 "### " 前缀**进了库。）

    没有 "### " 时才真的去量（纯 txt、没用标题样式的 docx 走这条）。
    反正管理端有预览，切得离谱一眼能看见、也不会落库。
    """
    by_question = split_qa_pairs_pdf(text)
    by_heading = split_qa_pairs_md(text)

    has_heading_marker = any(line.strip().startswith("### ") for line in text.split("\n"))
    if has_heading_marker or len(by_heading) > len(by_question):
        return {"strategy": "MD 标题式", "parsed": by_heading}
    return {"strategy": "问句式", "parsed": by_question}


def parse_question_file(file_name: str, file_bytes: bytes) -> dict:
    """
    按扩展名分派切题策略。返回 {"strategy": 策略名, "parsed": [题目字典, ...]}

    - .pdf              → 问句式（PDF 文本没有结构标记，只能按题面长相认）
    - .md / .markdown   → MD 标题式（结构写在文件里，最可靠）
    - .docx             → 标题样式译成 # 再切；没有标题样式的文档自动落问句式
    - .txt              → 两套都试，谁切得多用谁

    抛 ValueError = 文件类型不支持（调用方转成 400）。
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if ext in PDF_EXTENSIONS:
        return {"strategy": "问句式", "parsed": split_qa_pairs_pdf(_extract_pdf_text(file_bytes))}

    if ext in MD_EXTENSIONS:
        text = normalize_variants(file_bytes.decode("utf-8", errors="replace"))
        return {"strategy": "MD 标题式", "parsed": split_qa_pairs_md(text)}

    if ext in DOCX_EXTENSIONS:
        return _best_effort_split(_extract_docx_text(file_bytes))

    if ext in TEXT_EXTENSIONS:
        return _best_effort_split(normalize_variants(file_bytes.decode("utf-8", errors="replace")))

    raise ValueError(f"不支持的文件类型 .{ext}（仅支持 PDF / DOCX / MD / TXT）")


def summarize_parse(parsed: list[dict]) -> dict:
    """切题结果的**客观统计**——只报事实，不下结论

    （这里本来设计了一条"问号率"判据，想自动识别"文件结构对不上切题规则"。
     被数据否掉了：`AI面试项目问答清单.md` 是标准问答文档，题面却是
     "Q1：先用一句话介绍一下你的项目"——**一个问号都没有（0.0）**；
     而医疗项目的《面试文档.md》（小标题结构、不该按题导）反而有 0.235。
     判据连"好文件/坏文件"都分不开，留着只会误伤——
     跟 09-13 误杀 3 道真题同一个教训：判据要从反面样本的长相出发，不能想当然。）

    能给的客观信号：
    - max_answer_len：明显超出其余题的答案长度，通常意味着"后面的内容被粘进了一条"
    - empty_answer：这些题导进去参考答案是空的
    采信与否，交给人看首尾样例判断。
    """
    total = len(parsed)
    if total == 0:
        return {"avg_answer_len": 0, "max_answer_len": 0, "empty_answer": 0}
    answers = [len(p["reference_answer"]) for p in parsed]
    return {
        "avg_answer_len": sum(answers) // total,
        "max_answer_len": max(answers),
        "empty_answer": sum(1 for a in answers if a == 0),
    }


def build_items(
    parsed: list[dict],
    *,
    category: str,
    position_tag: str,
    difficulty: str = "medium",
    source: str = "file-import",
) -> list[dict]:
    """切好的题 + 导入参数 → 批量导入 items（对齐 QuestionBankCreate 契约）

    「分类/岗位/难度/来源」这些参数**不进切题器**：切题只管切，标签由调用方给——
    同一个 PDF 想导成不同分类，不用改切题代码。
    """
    items = []
    for p in parsed:
        chapter = p.get("chapter")
        items.append({
            "category": category,
            "position_tag": position_tag,
            "difficulty": difficulty,
            "question": p["question"],
            "reference_answer": p["reference_answer"] or None,
            "tags": [chapter] if chapter else None,
            "source": source,
        })
    return items
