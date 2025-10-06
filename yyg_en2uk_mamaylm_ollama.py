# -*- coding: utf-8 -*-
"""
Yes, Your Grace — EN→UK локалізація через віддалений Ollama (MamayLM).
- Читає англ. '1 string text = "..."' з дампа UABEA
- Підміняє переклад у translationText[target-index] (типово 3 = RU-слот)
- Працює з кешем EN→UK (JSON) і мапою line_no→UK (JSON), вміє продовжувати
- Дає інформативні принти прогресу

Залежності: pip install requests
"""

import os, re, json, time, argparse, sys
from typing import List, Tuple
import requests

# ---------- Налаштування/регекси ----------
PH_REGEX = re.compile(r'(\{[^}]*\}|%[sd]|\\n|\\r|\\t|\")')
BAD_MB = "ÐÑÂÃ¤¦¢"

SYSTEM_PROMPT = (
    "Ти — професійний локалізатор ігор. Перекладай з АНГЛІЙСЬКОЇ на УКРАЇНСЬКУ.\n"
    "Правила:\n"
    "1) Відповідай ЛИШЕ перекладом, без пояснень/лапок/код-блоків.\n"
    "2) Зберігай плейсхолдери без змін: {0}, {name}, %s, \\n, \\t, \\\".\n"
    "3) Пунктуація, регістр і перенос рядків мають збігатися зі входом."
)

# ---------- Утиліти ----------
def protect_placeholders(s: str):
    tokens = PH_REGEX.findall(s)
    repl = {}
    out = s
    for i, t in enumerate(tokens):
        key = f"__PH_{i}__"
        repl[key] = t
        out = out.replace(t, key)
    return out, repl

def unprotect_placeholders(s: str, repl: dict):
    for k, v in repl.items():
        s = s.replace(k, v)
    return s

def looks_mojibake(s: str) -> bool:
    return any(ch in s for ch in BAD_MB)

def escape_dump(s: str) -> str:
    # назад у формат UABEA (екранування)
    s = s.replace("\\","\\\\").replace("\"","\\\"")
    s = s.replace("\r","\\r").replace("\n","\\n").replace("\t","\\t")
    return s

def L(msg: str, log_file=None):
    print(msg, flush=True)
    if log_file:
        with open(log_file, "a", encoding="utf-8-sig") as f:
            f.write(msg + "\n")

# ---------- Парсер дампа ----------
def collect_blocks(lines: List[str], target_index: int) -> List[Tuple[int, str]]:
    """
    Повертає [(line_no_to_replace, english_text), ...] для кожного SpeechLine.
    line_no_to_replace — рядок '1 string data = "..."' у translationText[target_index]
    english_text — значення '1 string text = "..."' з того ж блоку
    """
    results = []
    in_block = False
    inside_array = False
    cur_idx = None
    line_to_replace = None
    en_text = None

    for i, line in enumerate(lines):
        if line.strip().endswith("SpeechLine data"):
            in_block = True
            inside_array = False
            cur_idx = None
            line_to_replace = None
            en_text = None
            continue

        if not in_block:
            continue

        m_en = re.match(r'^\s*1 string text = "(.*)"\s*$', line)
        if m_en:
            # ВАЖЛИВО: НЕ decode('unicode_escape') — рядок уже в Unicode
            en_text = m_en.group(1)
            continue

        if " 1 Array Array (" in line and "translationText" in lines[i-1]:
            inside_array = True
            cur_idx = None
            continue

        if inside_array:
            m_idx = re.match(r"^\s*\[(\d+)\]\s*$", line)
            if m_idx:
                cur_idx = int(m_idx.group(1))
                continue
            m_data = re.match(r'^\s*1 string data = "(.*)"\s*$', line)
            if m_data and cur_idx == target_index:
                line_to_replace = i
            # кінець масиву
            if ("customTranslationAudioClips" in line or
                "customTranslationLipsyncFiles" in line):
                inside_array = False
                cur_idx = None
                if line_to_replace is not None and en_text is not None:
                    results.append((line_to_replace, en_text))
    return results

# ---------- Ollama ----------
def ollama_chat(host: str, model: str, prompt: str, timeout: int = 120) -> str:
    url = f"http://{host}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": 8192
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    out = data["message"]["content"].strip()
    # якщо раптом модель повернула код-блок, знімаємо "огортку"
    if out.startswith("```"):
        out = out.strip("`")
        parts = [p for p in out.splitlines() if p.strip()]
        out = parts[-1] if parts else ""
    return out

def translate_one_ollama(host: str, model: str, text: str) -> str:
    prot, mp = protect_placeholders(text)
    uk = ollama_chat(host, model, prot)
    uk = unprotect_placeholders(uk, mp)
    if looks_mojibake(uk):
        try:
            uk = uk.encode("cp1252","strict").decode("utf-8","strict")
        except Exception:
            pass
    return uk

# ---------- Основна логіка ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Оригінальний UABEA dump (txt)")
    ap.add_argument("--output", required=True, help="Вихідний dump з УК (txt)")
    ap.add_argument("--host", required=True, help="Хост Ollama, напр. 192.168.1.130:11434")
    ap.add_argument("--model", required=True, help="Модель Ollama, напр. hf.co/INSAIT-Institute/...:Q8_0")
    ap.add_argument("--target-index", type=int, default=3, help="Який індекс у translationText підміняти (3 = RU-слот)")
    ap.add_argument("--batch-size", type=int, default=1, help="Скільки рядків перекладати за один цикл запитів (1 рекомендується)")
    ap.add_argument("--cache-file", default="en2uk_cache.json")
    ap.add_argument("--progress-file", default="line2uk_map.json")
    ap.add_argument("--log-file", default="yyg_mamaylm_ollama.log")
    ap.add_argument("--log-every", type=int, default=25, help="Як часто (кожні N рядків) друкувати прогрес")
    ap.add_argument("--fresh", action="store_true", help="Ігнорувати існуючі cache/progress і почати заново")
    args = ap.parse_args()

    t0 = time.time()
    L("=== Yes Your Grace EN→UK via Ollama (MamayLM) ===", args.log_file)

    # 1) читаємо дамп
    with open(args.input, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 2) збираємо пари
    pairs = collect_blocks(lines, args.target_index)
    total = len(pairs)
    L(f"Блоків знайдено: {total}", args.log_file)

    # 3) кеш/прогрес
    cache = {}
    line2uk = {}
    if not args.fresh and os.path.exists(args.cache_file):
        with open(args.cache_file, "r", encoding="utf-8-sig") as f:
            cache = json.load(f)
    if not args.fresh and os.path.exists(args.progress_file):
        with open(args.progress_file, "r", encoding="utf-8-sig") as f:
            line2uk = json.load(f)

    # 4) визначаємо списки
    already_done = len(line2uk)
    to_translate = []
    cached_hits = 0

    for ln, en in pairs:
        key = str(ln)
        if key in line2uk:
            continue
        uk_cached = cache.get(en)
        if uk_cached:
            line2uk[key] = uk_cached
            cached_hits += 1
        else:
            to_translate.append((ln, en))

    remain = len(to_translate)
    L(f"Вже готово (з минулих запусків): {already_done}", args.log_file)
    L(f"Хіти кешу цього разу: {cached_hits}", args.log_file)
    L(f"До перекладу зараз: {remain}", args.log_file)

    # 5) переклад порціями
    processed_now = 0
    i = 0
    try:
        while i < remain:
            batch = to_translate[i:i + args.batch_size]
            i += args.batch_size

            texts = [en for _, en in batch]
            lines_idx = [ln for ln, _ in batch]

            # викликаємо модель по одному (стабільніше для якості)
            results = []
            for en in texts:
                uk = translate_one_ollama(args.host, args.model, en)
                results.append(uk)

            # оновлюємо кеш/мапу
            for (ln, en), uk in zip(batch, results):
                cache[en] = uk
                line2uk[str(ln)] = uk
                processed_now += 1

                # Прогрес принт
                done_total = len(line2uk)
                if processed_now % args.log_every == 0:
                    pct = (done_total / total) * 100 if total else 100.0
                    L(f"[{done_total}/{total} = {pct:.1f}%]  (+{processed_now} цього запуску; кеш={len(cache)})",
                      args.log_file)

            # зберігаємо після кожного батча
            with open(args.cache_file, "w", encoding="utf-8-sig") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            with open(args.progress_file, "w", encoding="utf-8-sig") as f:
                json.dump(line2uk, f, ensure_ascii=False, indent=2)

    except KeyboardInterrupt:
        L("⛔ Перервано користувачем (Ctrl+C). Прогрес збережено.", args.log_file)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        L(f"HTTPError {code}: {e}. Прогрес збережено, можна перезапустити без --fresh.", args.log_file)

    # 6) збираємо вихідний дамп
    out = list(lines)
    replaced = 0
    for ln, _ in pairs:
        uk = line2uk.get(str(ln))
        if not uk:
            continue
        out[ln] = re.sub(r'(").*(")$', f'"{escape_dump(uk)}"', out[ln])
        replaced += 1

    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(out)

    t1 = time.time()
    done_total = len(line2uk)
    pct = (done_total / total) * 100 if total else 100.0
    L("----- ПІДСУМКИ -----", args.log_file)
    L(f"Підмінено у дампі: {replaced}/{total} ({pct:.1f}%)", args.log_file)
    L(f"Нових перекладів цього запуску: {processed_now}", args.log_file)
    L(f"Кеш EN→UK: {len(cache)} пар", args.log_file)
    L(f"Час роботи: {t1 - t0:.1f} c", args.log_file)
    L(f"Вихідний дамп: {args.output}", args.log_file)
    L(f"Кеш: {args.cache_file} | Прогрес: {args.progress_file} | Лог: {args.log_file}", args.log_file)

if __name__ == "__main__":
    main()
