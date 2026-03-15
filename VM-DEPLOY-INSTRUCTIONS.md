# Инструкция: Развёртывание агента на VM

## Проблема
Авточекер не нашёл `agent.py` на вашей VM `10.93.25.181`. Нужно развернуть код на VM.

## Шаг 1: Подключитесь к VM

```bash
ssh operator@10.93.25.181
# Пароль: 1234
```

## Шаг 2: Проверьте, есть ли репозиторий

```bash
ls ~/se-toolkit-lab-6/agent.py
```

**Если файл существует:**
```bash
cd ~/se-toolkit-lab-6
git fetch origin
git checkout 1234
git pull origin 1234
```

**Если файла нет (склонируйте ваш fork):**
```bash
cd ~
git clone https://github.com/<YOUR_GITHUB_USERNAME>/se-toolkit-lab-6
cd se-toolkit-lab-6
git checkout 1234
```

## Шаг 3: Создайте файлы окружения

```bash
cd ~/se-toolkit-lab-6

# Создайте .env.agent.secret
cp .env.agent.example .env.agent.secret

# Создайте .env.docker.secret
cp .env.docker.example .env.docker.secret
```

## Шаг 4: Заполните .env.agent.secret

```bash
nano .env.agent.secret
```

**Содержимое:**
```env
LLM_API_KEY=my-secret-qwen-key
LLM_API_BASE=http://10.93.25.181:42005/v1
LLM_MODEL=qwen3-coder-plus
```

## Шаг 5: Заполните .env.docker.secret

```bash
nano .env.docker.secret
```

**Содержимое:**
```env
# Эти значения должны совпадать с теми, что вы использовали при настройке backend
AUTOCHECKER_EMAIL=your-email@innopolis.university
AUTOCHECKER_PASSWORD=your-github-username-your-telegram-alias
LMS_API_KEY=<ваш-LMS_API_KEY-из-.env.docker.secret>
AGENT_API_BASE_URL=http://localhost:42002
```

## Шаг 6: Проверьте, что агент работает

```bash
cd ~/se-toolkit-lab-6

# Установите зависимости (если нужно)
python -m pip install httpx python-dotenv

# Запустите тестовый вопрос
python agent.py "What is 2+2?"
```

**Ожидаемый вывод:**
```json
{"answer": "2 + 2 = 4.", "source": "", "tool_calls": []}
```

## Шаг 7: Проверьте полный бенчмарк

```bash
cd ~/se-toolkit-lab-6
python run_eval.py
```

## Шаг 8: Если всё работает — авточекер пройдёт

После того как агент работает на VM, авточекер сможет его найти и проверить.

---

## Быстрая команда для копирования (все шаги вместе)

```bash
# Подключиться к VM
ssh operator@10.93.25.181
# Пароль: 1234

# На VM:
cd ~
if [ -d se-toolkit-lab-6 ]; then
    cd se-toolkit-lab-6
    git fetch origin
    git checkout 1234
    git pull origin 1234
else
    git clone https://github.com/<YOUR_GITHUB_USERNAME>/se-toolkit-lab-6
    cd se-toolkit-lab-6
    git checkout 1234
fi

# Создать конфиги
cp .env.agent.example .env.agent.secret
cp .env.docker.example .env.docker.secret

# Редактировать .env.agent.secret (вставьте свои значения)
nano .env.agent.secret

# Редактировать .env.docker.secret (вставьте свои значения)
nano .env.docker.secret

# Тест
python agent.py "What is 2+2?"
```
