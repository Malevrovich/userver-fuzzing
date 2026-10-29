# simple-grpc-target-service

Отдельный gRPC-аналог `simple-target-service`, созданный штатным генератором userver v3.2:

```sh
third_party/userver/scripts/userver-create-service --grpc services/simple-grpc-target-service
```

Контракт — [proto/fuzzing/targets.proto](proto/fuzzing/targets.proto).
В нём определены `fuzzing.target.TargetService` и внешняя зависимость
`fuzzing.target.DecisionService`. Сохранён `HelloService.SayHello` из шаблона.
Обычные protobuf-сообщения, без grpc-structs и без ручного protobuf/gRPC transport-кода.

## Штатный flow

- `userver_add_grpc_library` генерирует protobuf C++, userver `ServiceBase`/`Client`
  и Python stubs для testsuite из `.proto`.
- Обработчик наследует сгенерированный `TargetServiceBase::Component`.
- Внешний клиент хранится в стандартном `ugrpc::client::SimpleClientComponent`.
- В testsuite используются штатные `grpc_channel` и `grpc_mockserver`.
- Userver берётся из `../../third_party/userver` через `download_userver(TRY_DIR ...)`.
  При общей сборке уже созданный `userver::grpc` используется повторно.
- HTTP `/hello` из комбинированного шаблона удалён. HTTP остался только для
  `/ping` и testsuite `/tests/{action}`; все прикладные методы используют gRPC.

Локальные гайды:
[создание проекта](../../third_party/userver/scripts/docs/en/userver/build/build.md),
[gRPC tutorial](../../third_party/userver/scripts/docs/en/userver/tutorial/grpc_service.md),
[gRPC driver](../../third_party/userver/scripts/docs/en/userver/grpc/grpc.md),
[таймауты и повторы](../../third_party/userver/scripts/docs/en/userver/grpc/timeouts_retries.md).

## Сценарии

| RPC в TargetService | Контрольный дефект |
| --- | --- |
| `StatelessCrash` | `x=21, y=21` → `SIGABRT` |
| `StatelessError` | `mode=MODE_FAST, value=13` → `INTERNAL`; процесс остаётся жив |
| `Sequence` | `ACTION_BEGIN` → `ACTION_ADVANCE` → `ACTION_FINISH` → `SIGABRT` |
| `Prepare` + `Commit` | Подготовить `value=42`, затем дважды commit полученного ticket → `SIGABRT` |
| `DependencyCrash` | `MODE_FAST, value=13` и успешный `Decide` с `DECISION_RETRY` → `SIGABRT` |

Нормальные вызовы возвращают `OK`; намеренный `INTERNAL` — аналог HTTP 500.
Обязательные поля объявлены `optional` в proto3 для проверки presence: отсутствие,
неверный enum, число вне [0,100] или ticket вне 1–20 ASCII-цифр дают `INVALID_ARGUMENT`.
Ограничения приложения описаны комментариями в `.proto` и проверяются C++-кодом.
Неизвестные protobuf-поля обрабатываются стандартным protobuf, без специального запрета.

`ACTION_RESET` сбрасывает sequence. Новый `Prepare` инвалидирует предыдущий ticket
и сбрасывает commit. Эти два состояния независимы и защищены `engine::Mutex`.
Неизвестный ticket даёт `FAILED_PRECONDITION`. Перезапуск сбрасывает весь state.

Внешняя зависимость также gRPC: `DecisionService.Decide(ModeValue) -> Decision`.
Её endpoint — config var `decision-endpoint`, по умолчанию `localhost:8084`.
Принимаются только `DECISION_ACCEPT` и `DECISION_RETRY`. Некорректный ответ или
ошибка зависимости дают `UNAVAILABLE`, истёкший дедлайн — `DEADLINE_EXCEEDED`.
На вызов заданы `CallOptions.SetTimeout(500ms)` и `SetAttempts(1)`.

## Сборка и запуск

Рекомендуемый воспроизводимый Linux-путь — [.devcontainer](.devcontainer/README.md)
на официальном образе userver v3.2. Внутри контейнера из папки сервиса:

```sh
make build-debug
make test-debug
make start-debug
```

Сборка обоих стендов из корня репозитория:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 6
ctest --preset debug
```

Для нативной macOS нужны зависимости userver, OpenSSL 3 и Python 3.11.
Актуальный Homebrew protobuf 7 не поддерживается userver v3.2, поэтому macOS
preset использует штатные pinned-download опции userver для gRPC, protobuf,
Abseil и RE2. Отдельный `cmake/GrpcMacos.cmake` задаёт приоритет их заголовков
перед глобальными Homebrew includes. Принудительные includes и правки
исходников gRPC/userver не нужны.
Для grpcio-tools с protobuf 5 используется Python 3.11.
Если Homebrew сделал OpenSSL 4 глобальным, верни заголовки OpenSSL 3 через
`brew unlink openssl@4` и `brew link --force openssl@3`.
Если `python3.11` доступен в PATH:

```sh
cmake --preset macos-grpc-debug -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)"
cmake --build --preset macos-grpc-debug --parallel 6
ctest --preset macos-grpc-debug
```

Иной Python выбирается через `-DUSERVER_PYTHON_PATH=/path/to/python3.11`.
Профиль создаёт отдельный каталог `build/macos-grpc-debug`, не очищая прежние кеши.

Для самостоятельного запуска из корня репозитория:

```sh
./build/macos-grpc-debug/services/simple-grpc-target-service/simple_grpc_target_service \
  --config services/simple-grpc-target-service/configs/static_config.yaml \
  --config_vars services/simple-grpc-target-service/configs/config_vars.yaml
```

Порты: 8083 — gRPC, 8082 — HTTP health/tests-control; REST-стенд использует 8080.
Контракт можно передавать gRPC-инструментам напрямую, например:

```sh
grpcurl -plaintext -import-path services/simple-grpc-target-service/proto \
  -proto fuzzing/targets.proto -d '{"x":20,"y":22}' \
  localhost:8083 fuzzing.target.TargetService/StatelessCrash
```

Для запуска внешней зависимости после сборки можно использовать маленький
Python stub на тех же сгенерированных protobuf-классах:

```sh
PYTHONPATH="$PWD/build/macos-grpc-debug/services/simple-grpc-target-service/proto" \
  build/macos-grpc-debug/services/simple-grpc-target-service/venv-testsuite-simple_grpc_target_service/bin/python \
  services/simple-grpc-target-service/tools/decision_server.py --decision retry
```

С ним вызов `DependencyCrash` с `{"mode":"MODE_FAST","value":13}` завершит
процесс target. Параметр `--decision accept` отключает это условие падения.

Тесты проверяют обычные ответы, статусы, presence и диапазоны полей, reset,
общий state, gRPC-зависимость и дедлайн. Crash-тесты запускают отдельный процесс
и требуют `SIGABRT`; одного `UNAVAILABLE` от клиента недостаточно.
Core dumps отключены только в этих тестовых дочерних процессах.

Проверено 29 октября 2026 на macOS ARM64: сборка из локального userver v3.2,
gRPC 1.59.1, protobuf C++ 5.26.0, Python 3.11.15. gRPC pytest — 40 passed;
общий CTest двух стендов — 6/6, REST pytest — 60 passed. Отдельно проверена
цепочка с Python `decision_server.py`: безопасный запрос возвращает OK,
`MODE_FAST/value=13` с ответом RETRY завершает target через SIGABRT.
Полный Linux/devcontainer build в этой проверке не запускался.

## License

Исходный шаблон — [Apache-2.0](https://github.com/userver-framework/userver/blob/v3.2/LICENSE).
