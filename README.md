# Unity EN→UK Localization via LLM 

---

## 🇺🇦 Українською (UA)

**Коротко:** цей репозиторій містить артефакти локалізації гри **Yes, Your Grace**: кеш перекладів, мапу прогресу, згенерований дамп перекладених рядків та лог. Переклад виконано локально моделлю **MamayLM v1.0** через **Ollama**, а потім імпортовано назад у гру за допомогою **UABEAvalonia**. Підмінюється *ru-слот* перекладів (індекс **[3]**), 

### Що всередині
```
unity_en2uk_by_llm/
├─ en2uk_cache.json              # Кеш EN→UK (унікальні рядки → переклад)
├─ line2uk_map.json              # Мапа "номер рядка дампа → переклад"
├─ YesYourGrace_SpeechManager_uk.txt  # Дамп для імпорту в UABEA (перекладено у слот [3])
├─ yyg_mamaylm_ollama.log        # Лог роботи скрипта/прогрес
└─ README.md
```
---

## Інструкція (як відтворити на своєму ПК)

### Передумови
- **[UABEAvalonia](https://github.com/nesrak1/UABEA/)** (Unity Assets Bundle Extractor).
- **[Ollama](https://ollama.com/)** на вашому хості з завантаженою моделлю [MamayLM](https://huggingface.co/spaces/INSAIT-Institute/mamaylm-v1-blog):
  ```bash
  ollama run hf.co/INSAIT-Institute/MamayLM-Gemma-3-12B-IT-v1.0-GGUF:Q8_0
  ```
  Якщо плануєте мережевий доступ з іншого ПК:
  ```bash
  # Windows PowerShell/CMD
  setx OLLAMA_HOST "0.0.0.0:11434"
  # (а також відкрийте порт 11434/TCP у фаєрволі)
  ```
- **Python 3** + `requests` (для запуску скрипта).
- Встановлена гра написана на Unity, показано на прикладі **Yes, Your Grace** (Steam) 

### Крок 1 — Експорт діалогів із гри
1. У **UABEAvalonia** відкрийте файл:
   ```
   ...\Steam\steamapps\common\Yes, Your Grace\YesYourGrace_Data\resources.assets
   ```
2. Знайдіть **YesYourGrace_SpeechManager** → **Export Dump**.
3. Збережіть дамп у UTF-8 (не зберігайте в ANSI).

### Крок 2 — Переклад EN→UK через MamayLM (Ollama)
Переклад здійснюється скриптом, який:
- читає англійський текст з `1 string text = "..."`,
- перекладає **EN→UK** через **Ollama**,
- підміняє **індекс [3]** у масиві `translationText`,
- зберігає прогрес у `en2uk_cache.json` та `line2uk_map.json`.

**Запуск (приклад):**
```bat
python yyg_en2uk_mamaylm_ollama_refactored.py ^
  --input "YesYourGrace_SpeechManager.txt" ^
  --output "YesYourGrace_SpeechManager_uk.txt" ^
  --host 192.168.1.130:11434 ^
  --model "hf.co/INSAIT-Institute/MamayLM-Gemma-3-12B-IT-v1.0-GGUF:Q8_0" ^
  --target-index 3 ^
  --batch-size 1 ^
  --log-every 50
```
> Перший запуск можна з `--fresh`. Наступні — **без** `--fresh` (продовження з кешу).  
> Плейсхолдери (`{0}`, `%s`, `\n`, `\"`) зберігаються без змін.

### Крок 3 — Імпорт перекладу назад у гру
- У **UABEA**: **Import Dump** → оберіть `YesYourGrace_SpeechManager_uk.txt` → **Save**.
- У грі в налаштуваннях мови оберіть **russian** (бо замінили ru-слот).

---

## Поради та поширені проблеми
- **«Ð/Ñ…» (мьоджібейк)**: відкривайте/зберігайте JSON та дампи в **UTF-8** (для JSON бажано UTF-8 with BOM). Не використовуйте `decode('unicode_escape')` до тексту з дампа.
- **Ollama не відповідає**: перевірте `http://<host>:11434/api/version`, правила фаєрвола та що модель завантажена.
- **Не видно української**: переконайтеся, що підмінявся індекс **[3]** та в грі вибрано **russian**.
---


## Посилання
- 📖 Medium-стаття з повним гайдом: **[додайте ваше посилання]**
- ✈️ Телеграм-канал: **[додайте ваше посилання]**

