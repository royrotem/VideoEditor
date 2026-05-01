# הרצת האפליקציה ב‑VS Code

מדריך מפורט להפעלה מקומית של עורך הוידאו AI. הוא מכוון לקובץ
[`scripts/setup.sh`](../scripts/setup.sh) שעושה את הרוב, ולתשתיות
ה‑VS Code שמותקנות תחת `.vscode/`. אם משהו במדריך הזה לא תואם את
הקוד — הקוד מנצח, ואז צריך לעדכן את המדריך.

> Step-by-step guide for getting the AI Video Editor running locally
> in VS Code. The repo's `scripts/setup.sh` does most of the work
> automatically; everything below is "press this, see that".

---

## דרישות מקדימות

לפני שמתחילים, ודאו שמותקנים אצלכם:

| כלי                | למה                                          | התקנה (macOS / Linux)                                                          |
| ------------------ | -------------------------------------------- | ------------------------------------------------------------------------------ |
| **Docker Desktop** | מריץ את Postgres + Redis + MinIO             | <https://docs.docker.com/get-docker/>                                          |
| **uv**             | מנהל הסביבה של Python 3.11                   | `curl -LsSf https://astral.sh/uv/install.sh \| sh`                             |
| **pnpm**           | מנהל החבילות של ה‑frontend                   | `npm install -g pnpm` (Node 20+)                                               |
| **ffmpeg / ffprobe** | renderer + probe                          | `brew install ffmpeg` או `sudo apt install ffmpeg`                             |
| **VS Code**        | עורך + debugger                              | <https://code.visualstudio.com/>                                               |
| **Anthropic API key** | סוכני Claude                              | <https://console.anthropic.com/settings/keys>                                  |

> אין צורך להתקין Python ידנית. `uv` מתקין את 3.11 בעצמו.

---

## פתיחת הפרויקט ב‑VS Code

1. הריצו `git clone <repo-url> && code VideoEditor` — או פתחו את התיקייה דרך
   File → Open Folder.
2. ב‑VS Code יוצג באנר בפינה הימנית התחתונה: **"This workspace has
   extension recommendations"** — לחצו **Install All**. ההרחבות מותאמות
   להגדרות שב‑`.vscode/settings.json` (Ruff, Black, Prettier, Tailwind,
   Docker, Pylance).
3. אל תפתחו עדיין את ה‑terminal של VS Code — קודם נריץ setup.

---

## שלב 1: setup חד‑פעמי

יש שתי דרכים שעושות בדיוק אותו דבר. תבחרו אחת.

### דרך א' — דרך VS Code (מומלץ)

1. `Cmd/Ctrl + Shift + P` → **"Tasks: Run Task"** → **"Setup (one-time)"**.
2. הסקריפט יבדוק שכל הכלים מותקנים, יעלה את ה‑containers, יריץ את
   ה‑migrations, ויתקין dependencies.
3. אם אין לכם עדיין `ANTHROPIC_API_KEY` ב‑`.env`, הוא יבקש אותו
   במהלך הריצה. הדביקו את המפתח שלכם ולחצו Enter (אפשר גם לדלג ולערוך
   את `.env` ידנית אחר כך).

### דרך ב' — דרך terminal

```bash
make setup
```

הסקריפט מדפיס בקצרה כל שלב ועוצר ראשון לכשל עם הסבר מה לתקן. בטוח
להריץ אותו שוב — הוא idempotent.

לאחר סיום מוצלח תקבלו את ההודעה **"Setup complete."** עם הוראות
להמשך.

---

## שלב 2: הפעלת האפליקציה

### דרך א' — Task יחיד

`Cmd/Ctrl + Shift + B` (ברירת מחדל ל‑build) או:
`Cmd/Ctrl + Shift + P` → **"Tasks: Run Task"** → **"Start dev"**.

ה‑task מפעיל בו‑זמנית:

- `docker compose up -d` — Postgres / Redis / MinIO
- `uvicorn app.main:app --reload` — backend ב‑<http://localhost:8000>
- `next dev` — frontend ב‑<http://localhost:3000>

הלוגים מופיעים בטרמינל של VS Code ומועתקים גם ל‑`.dev-logs/`.

### דרך ב' — terminal

```bash
make dev
```

לעצירה: `Ctrl + C`. ה‑dev servers נסגרים; ה‑containers נשארים פעילים
(`make infra-down` לעצור גם אותם).

---

## שלב 3: פתיחת הדפדפן

פתחו <http://localhost:3000>.

הזרימה המלאה:

1. **דף הבית** — צרו פרויקט חדש.
2. **דף הפרויקט** — העלו קובץ וידאו (FFprobe + Vision Analyzer רצים
   אוטומטית; הסטטוס יתעדכן ל‑*"מוכן"*).
3. **שיחות עריכה** — תארו את הסרטון שאתם רוצים בעברית. הסוכן
   יענה בשיחה איטרטיבית.
4. כשהסוכן יגיע להסכמה, הוא יסיים עם הודעה שמתחילה ב‑*"סיכום:"* —
   זה ה‑signal לכפתור **"גזור brief"**.
5. **"תכנן עריכה"** → ה‑Editing Planner מפיק EDL.
6. **"הפק רנדר"** → ffmpeg רץ, התוצר עולה ל‑MinIO, ועוברים אוטומטית
   לדף הרנדרים שמציג את הסרטון בנגן.

> ה‑MinIO console זמין ב‑<http://localhost:9001> (משתמש: `videoeditor`,
> סיסמה: `videoeditor`) — שם תוכלו לראות את הקבצים הגולמיים ואת
> הרנדרים.

---

## הרצה עם debugger

`F5` או Run & Debug → בחרו אחד מ:

| קונפיגורציה                   | למה                                                             |
| ----------------------------- | --------------------------------------------------------------- |
| **Backend: uvicorn (debug)**  | uvicorn עם debugpy מחובר; שימו breakpoint על endpoint            |
| **Backend: pytest (current file)** | הריצו את ה‑test file שפתוח עם debugger                       |
| **Backend: pytest (full suite)**   | הריצו את כל הסוויטה עם debugger                              |
| **Backend: Celery worker**    | worker בנפרד — שימושי כש‑`CELERY_EAGER=false`                   |
| **Frontend: open in Chrome**  | פותח Chrome שמחובר ל‑sourcemaps של Next.js                       |
| **Backend + Frontend** (compound) | מפעיל את שני הראשונים יחד                                    |

---

## הרצת בדיקות

| מטרה                  | פקודה              | task                                  |
| --------------------- | ------------------ | ------------------------------------- |
| הכל                   | `make test`        | "Run all tests"                       |
| backend only          | `make backend-test`| "Backend: pytest"                     |
| frontend only         | `make frontend-test`| "Frontend: vitest"                   |
| backend lint + types  | —                  | "Backend: ruff + black + mypy"        |
| frontend lint + types | —                  | "Frontend: typecheck + lint"          |
| smoke מקצה לקצה        | `make smoke`       | "Smoke test (against running stack)"  |

> **לפני push**: כדאי שכל ה‑tasks הללו יעברו ירוק. אותו דבר רץ ב‑CI.

---

## פתרון תקלות

### "Docker daemon is not running"

הפעילו את Docker Desktop (או `sudo systemctl start docker` ב‑Linux),
חכו עד שהאייקון יציב, ואז `make setup` שוב.

### "ANTHROPIC_API_KEY is unset"

ה‑backend מסתדר בלי המפתח לכל מה שלא קשור ל‑LLM (project CRUD,
upload). ברגע שתפתחו שיחה תקבלו 502; ערכו את `.env` בשורש הפרויקט
והוסיפו את המפתח, ואז restart ל‑backend.

### "port 5432/6379/9000 already in use"

יש לכם Postgres/Redis/MinIO רץ על המכונה. אופציות:

- עצרו אותם זמנית.
- או עדכנו את הפורטים ב‑`infra/docker-compose.yml` ובמקביל
  ב‑`.env`.

### Migrations failed

אם שיניתם schema והם לא מסונכרנים:

```bash
docker compose -f infra/docker-compose.yml down -v   # מוחק data!
make setup
```

### "Tests failed on a clean checkout"

```bash
cd backend && uv sync --all-extras --dev
cd ../frontend && pnpm install
```

ולאחר מכן הריצו את ה‑tasks "Backend: pytest" ו‑"Frontend: vitest"
שוב. אם נשאר משהו אדום, פתחו issue או שלחו את הלוגים מ‑`.dev-logs/`.

---

## נקיון

| מצב                                    | פקודה                |
| -------------------------------------- | -------------------- |
| לעצור dev servers, להשאיר infra        | `Ctrl + C` ב‑terminal|
| לעצור גם את ה‑containers (data נשמר)   | `make infra-down`    |
| למחוק caches + node_modules            | `make clean`         |
| למחוק את כל ה‑data (DB / MinIO)        | `docker compose -f infra/docker-compose.yml down -v` |
