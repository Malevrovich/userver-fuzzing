# userver-fuzzing

Минимальная основа проекта: userver из исходников и один сервис с функциональным
тестом через testsuite. Постановка фаззинга — в [PROJECT.md](PROJECT.md), обзор
инструментов — в [RESEARCH.md](RESEARCH.md).

## Структура

- `third_party/userver/` — git submodule официального репозитория, тег `v3.2`.
- `services/minimal/` — сервис `minimal-service`, конфигурация и testsuite-тест.
- `CMakeLists.txt` — общая сборка userver и сервисов через `add_subdirectory`.
- `CMakePresets.json` — параметры сборки; локальные настройки можно задать
  в игнорируемом `CMakeUserPresets.json`.
- `build/` — бинарники, Python-окружения, кеши и результаты тестов, вне git.

Сервис использует встроенный обработчик `GET /ping`: HTTP 200 с пустым телом.
Компоненты `TestsuiteSupport` и `TestsControl` обеспечивают интеграцию с testsuite;
`/tests/{action}` включается только при запуске через testsuite.

## Сборка и функциональный тест

Нужны Git, CMake >= 3.24, Ninja, компилятор C++20, Python >= 3.10 и
[зависимости userver для своей ОС](https://userver.tech/de/db9/md_en_2userver_2build_2dependencies.html).
Testsuite устанавливается штатной CMake-интеграцией в виртуальные окружения
внутри `build/`. Драйверы БД, gRPC, примеры и собственные тесты userver отключены.

Базовый вариант для Linux (в том числе x86-64 серверов и виртуальных машин):

```sh
git submodule update --init --recursive
cmake --preset debug
cmake --build --preset debug --parallel 6
ctest --preset debug
```

Число параллельных задач выбирай под доступные CPU и память. Архитектура
определяется компилятором; проект не задаёт `-march=native` или конкретную ISA.

macOS — отдельный вариант с пресетом `macos-debug`:

Для Homebrew ICU выполни рекомендованную документацией userver команду
`brew link --force icu4c` (на этой машине пакет называется `icu4c@78`).
Также нужен `openssl@3`: userver `v3.2` не линкуется с установленным здесь
OpenSSL 4. При первой конфигурации явно выбираем OpenSSL 3; CMake сохраняет
этот выбор в локальном каталоге сборки.

```sh
git submodule update --init --recursive
cmake --preset macos-debug -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)"
cmake --build --preset macos-debug --parallel 6
ctest --preset macos-debug
```

Функциональный тест сам запускает настоящий процесс сервиса, обращается к
`/ping` через HTTP и проверяет статус и тело ответа. Подробный вывод:

```sh
ctest --preset debug --verbose
```

Для ручного запуска из корня репозитория:

```sh
./build/debug/services/minimal/minimal-service --config services/minimal/configs/config.yaml
```

В другом терминале:

```sh
curl -i http://localhost:8080/ping
```

Для macOS в командах выше замени `debug` на `macos-debug`.

## Изменения userver

Исходники в submodule можно редактировать и пересобирать вместе с сервисом.
Перед коммитами создай рабочую ветку внутри `third_party/userver/`;
исходный checkout закреплён на теге и находится в detached HEAD.
Чтобы использовать свой форк, замени URL submodule и синхронизируй его через
`git submodule sync`. После коммита в userver основной репозиторий фиксирует
новую ссылку командой `git add third_party/userver`.

Для сборки с другим checkout или worktree:

```sh
cmake --preset debug -DUSERVER_SOURCE_DIR=/absolute/path/to/userver
```

Разные варианты userver лучше собирать в отдельных каталогах, например
с дополнительным `-B build/userver-experiment`.

## Документация userver

- [Настройка и сборка](https://userver.tech/de/dab/md_en_2userver_2build_2build.html).
- [Минимальный HTTP-сервис](https://userver.tech/da/d16/md_en_2userver_2tutorial_2hello__service.html).
- [Функциональные тесты](https://userver.tech/df/d07/md_en_2userver_2functional__testing.html).
- [Опции сборки](https://userver.tech/d5/d3d/md_en_2userver_2build_2options.html).

## Проверенный запуск

Сборка и функциональный тест выполнены на macOS ARM64 с AppleClang 21,
Python 3.14.6, OpenSSL 3.6.3 и yandex-taxi-testsuite 0.4.11.
Userver закреплён на коммите `19472cc41deda3fb1c7aa7d13d53235a0161a224` (`v3.2`).
Результат: `test_ping PASSED`, CTest — 1/1.
Linux/x86-64 пока не проверен; специфичных для ARM настроек в проекте нет.
