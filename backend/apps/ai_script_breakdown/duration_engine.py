import copy
import json
import math
import re


DEFAULT_DIALOGUE_DURATION_CONFIG = {
    "base": {
        "zh_chars_per_second": 4.2,
        "en_words_per_second": 2.6,
        "other_chars_per_second": 3.4,
        "min_dialogue_seconds": 0.8,
        "non_dialogue_line_seconds": 1.2,
    },
    "punctuation_pauses": {
        "，": 0.15,
        "、": 0.1,
        "。": 0.35,
        "？": 0.45,
        "！": 0.4,
        "；": 0.25,
        "：": 0.2,
        "…": 0.35,
        ",": 0.12,
        ".": 0.25,
        "?": 0.35,
        "!": 0.35,
        ";": 0.2,
        ":": 0.18,
    },
    "emotion_pauses": {
        "neutral": 0,
        "calm": 0,
        "sad": 0.25,
        "angry": 0.2,
        "fear": 0.3,
        "surprised": 0.2,
        "hesitant": 0.45,
        "crying": 0.6,
    },
    "speed_multipliers": {
        "slow": 1.25,
        "normal": 1,
        "fast": 0.82,
    },
    "action_durations": {
        "none": 0,
        "look": 0.4,
        "turn": 0.5,
        "walk": 0.8,
        "run": 1.1,
        "sit": 0.7,
        "stand": 0.6,
        "gesture": 0.5,
        "fight": 1.4,
        "fallback": 0.6,
    },
    "pause": {
        "needed_seconds": 0.6,
        "not_needed_seconds": 0,
    },
    "round_to": 1,
}

SHOT_LINE_RE = re.compile(r"^\s*【([^】]+)】【([^】]+)】(?:【([^】]+)】)?\s*$")
QUOTE_RE = re.compile(r"[“\"]([^”\"]+)[”\"]|‘([^’]+)’|'([^']+)'")
EN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
SPEECH_VERB_RE = re.compile(r"(?:说|喊|问|答|道|念|叫|嘀咕|低声|高声|怒吼|解释|提醒|追问|回应|开口|喃喃)[^：:]{0,8}[：:]\s*(.+)$")


def dialogue_duration_config_json() -> str:
    return json.dumps(DEFAULT_DIALOGUE_DURATION_CONFIG, ensure_ascii=False, indent=2)


def load_dialogue_duration_config(raw_value: str | None = None) -> dict:
    config = copy.deepcopy(DEFAULT_DIALOGUE_DURATION_CONFIG)
    if not raw_value:
        return config
    try:
        custom = json.loads(str(raw_value))
    except (TypeError, ValueError):
        return config
    if isinstance(custom, dict):
        _deep_update(config, custom)
    return config


def prepare_segment_item(item: dict, config: dict) -> dict:
    prepared = copy.deepcopy(item)
    prepared_lines = prepare_shot_lines(prepared.get("shot_lines") or [], config)
    prepared["shot_lines"] = prepared_lines
    prepared["_calculated_duration_seconds"] = sum(line.get("_total_duration_seconds", 0) for line in prepared_lines)
    prepared["estimated_duration"] = int(math.ceil(prepared["_calculated_duration_seconds"]))
    prepared["copy_text"] = ""
    return prepared


def split_segment_item(item: dict, max_seconds: int, config: dict) -> list[dict]:
    prepared = prepare_segment_item(item, config)
    lines = []
    for line in prepared.get("shot_lines") or []:
        lines.extend(_split_long_line(line, max_seconds, config))
    if not lines:
        return [prepared]

    chunks = []
    current = []
    current_seconds = 0.0
    for line in lines:
        line_seconds = float(line.get("_total_duration_seconds") or 0)
        if current and math.ceil(current_seconds + line_seconds) > max_seconds:
            chunks.append(current)
            current = []
            current_seconds = 0.0
        current.append(line)
        current_seconds += line_seconds
    if current:
        chunks.append(current)

    if len(chunks) == 1:
        prepared["shot_lines"] = chunks[0]
        prepared["_calculated_duration_seconds"] = sum(line.get("_total_duration_seconds", 0) for line in chunks[0])
        prepared["estimated_duration"] = int(math.ceil(prepared["_calculated_duration_seconds"]))
        return [prepared]

    split_items = []
    title = str(prepared.get("segment_title") or "").strip()
    for index, chunk in enumerate(chunks, start=1):
        split_item = copy.deepcopy(prepared)
        split_item["segment_title"] = f"{title}-{index}" if title else ""
        split_item["shot_lines"] = chunk
        split_item["_calculated_duration_seconds"] = sum(line.get("_total_duration_seconds", 0) for line in chunk)
        split_item["estimated_duration"] = int(math.ceil(split_item["_calculated_duration_seconds"]))
        split_item["copy_text"] = ""
        if index > 1:
            split_item["continuity_from_previous"] = True
            split_item["previous_anchor_line"] = ""
        split_items.append(split_item)
    return split_items


def prepare_shot_lines(shot_lines: list[dict], config: dict) -> list[dict]:
    prepared = []
    for raw_line in shot_lines:
        if not isinstance(raw_line, dict):
            continue
        line = copy.deepcopy(raw_line)
        _hydrate_line_fields(line)
        breakdown = calculate_line_duration(line, config)
        line["_duration_breakdown"] = breakdown
        line["_dialogue_duration_seconds"] = breakdown["dialogue_total"]
        line["_total_duration_seconds"] = breakdown["total"]
        line["line_text"] = build_line_text(line, breakdown["dialogue_total"])
        prepared.append(line)
    return prepared


def calculate_line_duration(line: dict, config: dict) -> dict:
    dialogue = str(line.get("dialogue") or "").strip()
    action = str(line.get("action") or line.get("action_type") or "").strip()
    description = str(line.get("description") or "")
    emotion = _normalize_emotion(line.get("emotion"))
    speed = _normalize_speed(line.get("speech_speed") or line.get("speed"))
    needs_pause = _truthy(line.get("needs_pause") or line.get("need_pause") or line.get("pause"))

    base_config = config.get("base") or {}
    if dialogue:
        base = _base_dialogue_seconds(dialogue, base_config)
        punctuation = _punctuation_seconds(dialogue, config.get("punctuation_pauses") or {})
        emotion_pause = float((config.get("emotion_pauses") or {}).get(emotion, 0) or 0)
        speed_multiplier = float((config.get("speed_multipliers") or {}).get(speed, 1) or 1)
        pause = _pause_seconds(needs_pause, config)
        dialogue_total = (base * speed_multiplier) + punctuation + emotion_pause + pause
        non_dialogue = 0
    else:
        base = 0
        punctuation = 0
        emotion_pause = 0
        speed_multiplier = 1
        pause = _pause_seconds(needs_pause, config)
        dialogue_total = 0
        non_dialogue = float(base_config.get("non_dialogue_line_seconds", 1.2) or 1.2)
    action_seconds = _action_seconds(action or description, config.get("action_durations") or {})
    total = max(0.1, dialogue_total + action_seconds + non_dialogue)
    return {
        "base": round(base, 3),
        "punctuation": round(punctuation, 3),
        "emotion_pause": round(emotion_pause, 3),
        "speed_multiplier": round(speed_multiplier, 3),
        "action": round(action_seconds, 3),
        "pause": round(pause, 3),
        "non_dialogue": round(non_dialogue, 3),
        "dialogue_total": _rounded_seconds(dialogue_total, config),
        "total": _rounded_seconds(total, config),
    }


def build_line_text(line: dict, dialogue_seconds: float) -> str:
    shot_size = str(line.get("shot_size") or "中景").strip("【】") or "中景"
    description = str(line.get("description") or "").strip()
    if not description:
        return ""
    dialogue = str(line.get("dialogue") or "").strip()
    if dialogue:
        return f"【{shot_size}】【{description}】【{_format_seconds(dialogue_seconds)}】"
    return f"【{shot_size}】【{description}】"


def _deep_update(target: dict, source: dict) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _hydrate_line_fields(line: dict) -> None:
    line_text = str(line.get("line_text") or "").strip()
    match = SHOT_LINE_RE.match(line_text)
    if match:
        if not str(line.get("shot_size") or "").strip():
            line["shot_size"] = match.group(1)
        if not str(line.get("description") or "").strip():
            line["description"] = match.group(2)
    if not str(line.get("dialogue") or "").strip():
        text = str(line.get("description") or line_text or "")
        dialogue = _extract_dialogue_from_text(text, line)
        if dialogue:
            line["dialogue"] = dialogue
    dialogue = str(line.get("dialogue") or "").strip()
    if match and dialogue and dialogue not in str(line.get("description") or ""):
        line["description"] = match.group(2)


def _extract_dialogue_from_text(text: str, line: dict) -> str:
    content = str(text or "").strip()
    quote = QUOTE_RE.search(content)
    if quote:
        return _clean_dialogue(next(group for group in quote.groups() if group))

    character = str(line.get("character") or "").strip()
    if character:
        character_match = re.search(rf"{re.escape(character)}[^：:]{{0,16}}[：:]\s*(.+)$", content)
        if character_match:
            return _clean_dialogue(character_match.group(1))

    speech_match = SPEECH_VERB_RE.search(content)
    if speech_match:
        return _clean_dialogue(speech_match.group(1))
    return ""


def _clean_dialogue(value: str) -> str:
    text = str(value or "").strip().strip("“”\"'‘’")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip("，。；：: ")


def _base_dialogue_seconds(dialogue: str, config: dict) -> float:
    zh_chars = len(CJK_RE.findall(dialogue))
    en_words = len(EN_WORD_RE.findall(dialogue))
    counted = zh_chars + sum(len(word) for word in EN_WORD_RE.findall(dialogue))
    other_chars = len([ch for ch in dialogue if not ch.isspace() and ch.isalnum()]) - counted
    zh_rate = float(config.get("zh_chars_per_second", 4.2) or 4.2)
    en_rate = float(config.get("en_words_per_second", 2.6) or 2.6)
    other_rate = float(config.get("other_chars_per_second", 3.4) or 3.4)
    seconds = 0.0
    if zh_chars:
        seconds += zh_chars / max(zh_rate, 0.1)
    if en_words:
        seconds += en_words / max(en_rate, 0.1)
    if other_chars > 0:
        seconds += other_chars / max(other_rate, 0.1)
    minimum = float(config.get("min_dialogue_seconds", 0.8) or 0.8)
    return max(seconds, minimum)


def _punctuation_seconds(text: str, pauses: dict) -> float:
    return sum(float(pauses.get(ch, 0) or 0) for ch in text)


def _normalize_emotion(value) -> str:
    text = str(value or "neutral").strip().lower()
    if any(word in text for word in ["怒", "angry", "rage"]):
        return "angry"
    if any(word in text for word in ["悲", "sad"]):
        return "sad"
    if any(word in text for word in ["怕", "恐", "fear", "scared"]):
        return "fear"
    if any(word in text for word in ["惊", "surprise"]):
        return "surprised"
    if any(word in text for word in ["犹豫", "迟疑", "hesitat"]):
        return "hesitant"
    if any(word in text for word in ["哭", "泣", "cry"]):
        return "crying"
    if any(word in text for word in ["平静", "calm"]):
        return "calm"
    return text if text else "neutral"


def _normalize_speed(value) -> str:
    text = str(value or "normal").strip().lower()
    if any(word in text for word in ["快", "急", "fast", "rapid"]):
        return "fast"
    if any(word in text for word in ["慢", "缓", "slow"]):
        return "slow"
    return "normal"


def _action_seconds(action: str, durations: dict) -> float:
    text = str(action or "").strip().lower()
    if not text:
        return float(durations.get("none", 0) or 0)
    keyword_map = {
        "look": ["看", "望", "凝视", "look", "stare"],
        "turn": ["转身", "回头", "turn"],
        "walk": ["走", "靠近", "walk", "approach"],
        "run": ["跑", "冲", "奔", "run", "rush"],
        "sit": ["坐", "sit"],
        "stand": ["站", "起身", "stand"],
        "gesture": ["手势", "挥手", "指向", "gesture", "point"],
        "fight": ["打", "斗", "挥剑", "fight", "hit"],
    }
    for key, keywords in keyword_map.items():
        if key == text or any(keyword in text for keyword in keywords):
            return float(durations.get(key, durations.get("fallback", 0.6)) or 0)
    return float(durations.get(text, durations.get("fallback", 0.6)) or 0)


def _pause_seconds(needs_pause: bool, config: dict) -> float:
    pause_config = config.get("pause") or {}
    key = "needed_seconds" if needs_pause else "not_needed_seconds"
    return float(pause_config.get(key, 0) or 0)


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "需要", "是", "pause", "停顿"}


def _rounded_seconds(value: float, config: dict) -> float:
    digits = int(config.get("round_to", 1) or 1)
    return round(max(value, 0), digits)


def _format_seconds(value: float) -> str:
    rounded = round(float(value or 0), 1)
    if rounded.is_integer():
        return f"{int(rounded)}秒"
    return f"{rounded}秒"


def _split_long_line(line: dict, max_seconds: int, config: dict) -> list[dict]:
    if math.ceil(float(line.get("_total_duration_seconds") or 0)) <= max_seconds:
        return [line]
    dialogue = str(line.get("dialogue") or "").strip()
    if not dialogue:
        return [line]
    pieces = _dialogue_pieces(dialogue)
    if len(pieces) <= 1:
        return [line]

    split_lines = []
    current = ""
    for piece in pieces:
        candidate = current + piece
        candidate_line = _clone_line_with_dialogue(line, candidate)
        candidate_prepared = prepare_shot_lines([candidate_line], config)[0]
        if current and math.ceil(float(candidate_prepared.get("_total_duration_seconds") or 0)) > max_seconds:
            split_lines.append(prepare_shot_lines([_clone_line_with_dialogue(line, current)], config)[0])
            current = piece
        else:
            current = candidate
    if current:
        split_lines.append(prepare_shot_lines([_clone_line_with_dialogue(line, current)], config)[0])
    return split_lines or [line]


def _dialogue_pieces(dialogue: str) -> list[str]:
    pieces = re.findall(r"[^，。？！；：,.?!;:…]+[，。？！；：,.?!;:…]*", dialogue)
    return [piece for piece in pieces if piece]


def _clone_line_with_dialogue(line: dict, dialogue: str) -> dict:
    cloned = copy.deepcopy(line)
    original_dialogue = str(line.get("dialogue") or "")
    original_description = str(line.get("description") or "")
    cloned["dialogue"] = dialogue
    if original_dialogue and original_dialogue in original_description:
        cloned["description"] = original_description.replace(original_dialogue, dialogue, 1)
    else:
        cloned["description"] = f"{original_description}“{dialogue}”"
    cloned["line_text"] = ""
    return cloned
