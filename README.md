# userver-fuzzing

Стенд для знакомства с готовыми фаззерами и экспериментов с grey-box фаззингом
userver. Постановка проекта — в [PROJECT.md](PROJECT.md), обзор инструментов —
в [RESEARCH.md](RESEARCH.md).

## Сервис из официального шаблона

`services/simple-target-service/` создан штатным генератором userver `v3.2`:

```sh
third_party/userver/scripts/userver-create-service services/simple-target-service
```

Команда приведена для воспроизведения: целевая папка не должна существовать.
Выбран HTTP без БД. Прежний `services/minimal/` удалён.

В шаблоне есть обработчик `GET,POST /hello?name=Tester` с ответом
`Hello, Tester!\n`, проверка готовности `/ping`, C++ unit-тест, benchmark,
функциональный тест через testsuite, конфиги, Makefile и Dev Container.
Базовая ручка `/hello` оставлена из генератора. Добавлены ручные JSON-ручки
с намеренными дефектами для фаззинга: [описание и воспроизведение](services/simple-target-service/README.md).
Контракт — [OpenAPI 3.0.3](services/simple-target-service/openapi.yaml), серверный кодген не используется.
В `CMakeLists.txt` путь в `download_userver(TRY_DIR ...)` указывает на
`../../third_party/userver`. Штатный helper подключает этот checkout через
`add_subdirectory` и завершает работу без скачивания userver.
В корневых presets и presets сервиса задано
`CMAKE_DISABLE_FIND_PACKAGE_userver=ON`, чтобы использовать исходники даже при
наличии установленного userver. Корневой CMake проверяет наличие submodule.

## Варианты генератора

| Флаги | Результат |
| --- | --- |
| без флагов | HTTP-сервис с `/hello`, без БД; выбран для первого этапа |
| `--postgresql` | HTTP и пример работы с PostgreSQL, схема, данные и тесты |
| `--mongo` | HTTP и пример работы с MongoDB, настройки и тесты |
| `--grpc` | Дополнительно gRPC-сервис, `.proto` и функциональный тест |

Флаги можно сочетать, например `--grpc --postgresql`. Старые отдельные GitHub
репозитории `service_template`, `pg_service_template`, `pg_grpc_service_template`
и `mongo_grpc_service_template` в документации помечены как legacy:
для нового проекта рекомендуется генератор.

Основные локальные источники:

- [Configure, Build and Install](third_party/userver/scripts/docs/en/userver/build/build.md) — создание и запуск шаблона;
- [Writing your first HTTP server](third_party/userver/scripts/docs/en/userver/tutorial/hello_service.md) — устройство сервиса;
- [Functional tests](third_party/userver/scripts/docs/en/userver/functional_testing.md) — testsuite;
- [Supported platforms and templates](third_party/userver/scripts/docs/en/userver/supported_platforms.md) — статус старых шаблонов.

## Сборка и тесты

Нужны Git, CMake >= 3.24, Ninja, компилятор C++20, Python >= 3.10 и
[зависимости userver](third_party/userver/scripts/docs/en/userver/build/dependencies.md).

Из корня репозитория на Linux:

```sh
git submodule update --init --recursive
cmake --preset debug
cmake --build --preset debug --parallel 6
ctest --preset debug
```

На macOS с Homebrew OpenSSL 3:

```sh
git submodule update --init --recursive
cmake --preset macos-debug -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)"
cmake --build --preset macos-debug --parallel 6
ctest --preset macos-debug
```

Root presets собирают сервис, unit-тест и benchmark. Testsuite создаёт
виртуальные окружения внутри `build/` и запускает настоящий процесс сервиса.
Число параллельных задач выбирай под доступные CPU и память.

Проверено 29 октября 2026 на macOS ARM64 с userver `v3.2`: сборка прошла,
CTest — 3/3 (`simple_target_service_unittest`, `simple_target_service_benchmark`,
`testsuite-simple_target_service`). Linux и самостоятельные Makefile-presets
шаблона в этой проверке не запускались.

Для запуска в окружении testsuite без остановки после теста:

```sh
cmake --build build/macos-debug --target start-simple_target_service
```

В другом терминале:

```sh
curl 'http://127.0.0.1:8080/hello?name=userver'
```

Для Linux замени `macos-debug` на `debug`. Остановить сервис можно через Ctrl+C.

Штатный самостоятельный flow из папки сервиса — `make build-debug`,
`make test-debug`, `make start-debug`. Он использует собственные presets
шаблона; профиль `debug` включает ASan/UBSan. Корневые presets предназначены
для общей сборки стендов с нашим checkout userver. Сгенерированные файлы
`.github/` внутри папки сервиса являются заготовками для отдельного репозитория
и не запускают CI этого репозитория.

## Изменения userver

`third_party/userver/` — submodule официального репозитория на теге `v3.2`,
коммит `19472cc41deda3fb1c7aa7d13d53235a0161a224`.
Перед изменениями создай ветку внутри submodule. Для отправки своих изменений
можно заменить remote на свой форк; основной репозиторий фиксирует коммит
userver вместе с версией стенда.

Разные версии и профили инструментации лучше собирать в отдельных каталогах.
