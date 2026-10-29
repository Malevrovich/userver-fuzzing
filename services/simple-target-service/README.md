# simple_target_service

HTTP-сервис без БД, созданный официальным `userver-create-service` из userver
`v3.2`. Команда из корня репозитория:

```sh
third_party/userver/scripts/userver-create-service services/simple-target-service
```

Базовый `/hello` оставлен из шаблона. Дополнительно написаны вручную JSON-ручки
для фаззинга, без серверного кодгена. В `CMakeLists.txt` изменена строка
подключения userver, добавлены исходники и зависимость проверки OpenAPI в тестах:

```cmake
download_userver(TRY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/userver")
```

Штатный helper находит локальный checkout, подключает его через `add_subdirectory`
и не скачивает userver. В `CMakePresets.json` добавлен только
`CMAKE_DISABLE_FIND_PACKAGE_userver=ON`, чтобы установленный пакет не подменял
исходники. Если локальная папка отсутствует, штатный helper может перейти к
скачиванию; общая сборка из корня репозитория предварительно проверяет submodule.

## Интерфейс

- `GET /hello?name=userver` → `Hello, userver!\n`;
- `POST /hello?name=userver` → `Hello, userver!\n`;
- без `name` → `Hello, unknown user!\n`;
- `GET /ping` — проверка готовности.

Контракт всех ручек — [openapi.yaml](openapi.yaml), OpenAPI 3.0.3. Его можно
передать фаззеру как локальный файл; отдельной HTTP-ручки для схемы нет.

## Намеренные дефекты

Все новые ручки принимают JSON через POST. Числовые поля `x`, `y`, `value`
ограничены целыми значениями от 0 до 100. Неизвестные поля, неверные типы,
значения вне диапазона и невалидный JSON дают 400 без изменения состояния.

| Сценарий | Ручка | Условие сбоя |
| --- | --- | --- |
| Без состояния, падение процесса | `/stateless/crash` | `{"x":21,"y":21}`; проверяются сумма 42 и равенство чисел |
| Без состояния, HTTP 500 | `/stateless/error` | `{"mode":"fast","value":13}`; обычное C++-исключение, процесс продолжает работать |
| Одна ручка с состоянием | `/stateful/sequence` | Три запроса: `begin` → `advance` → `finish` в поле `action` |
| Две ручки с общим состоянием | `/shared/prepare`, `/shared/commit` | Подготовить `value=42`, затем дважды закоммитить полученный `ticket` |
| Запрос и ответ внешней зависимости | `/dependency/crash` | `{"mode":"fast","value":13}` и HTTP 200 с `{"decision":"retry"}` от зависимости |

Падения реализованы явным `std::abort()` и воспроизводятся в Debug и Release.
Это контрольные дефекты, а не неопределённое поведение или случайные сбои.
500 и падения не объявлены допустимыми ответами OpenAPI: фаззер должен
считать их нарушением контракта. Точные условия сбоя приведены здесь,
а в схеме описано предполагаемое корректное поведение API.

Примеры запросов, каждый crash-сценарий запускается после старта сервиса:

```sh
curl -X POST localhost:8080/stateless/crash -H 'Content-Type: application/json' -d '{"x":21,"y":21}'
curl -X POST localhost:8080/stateless/error -H 'Content-Type: application/json' -d '{"mode":"fast","value":13}'
```

Для `/stateful/sequence` отправь по очереди:

```json
{"action":"begin"}
{"action":"advance"}
{"action":"finish"}
```

`begin` начинает последовательность заново; `reset` сбрасывает её в `idle`.
`advance` из любого состояния, кроме `begun`, также сбрасывает её в `idle`.
`finish` без предшествующих `begin` и `advance` безопасен.

Для общего состояния отправь `{"value":42}` на `/shared/prepare` и сохрани
`ticket` из ответа. Затем дважды отправь `{"ticket":"<полученный ticket>"}`
на `/shared/commit`. Первый commit вернёт 200, второй завершит процесс.
Для значений, отличных от 42, повторные commit безопасны.
Неизвестный/устаревший ticket даёт 409. Новый prepare отменяет старый ticket
и сбрасывает признак commit; OpenAPI links описывают передачу ticket и повтор commit.

Оба сценария со state имеют независимое состояние в памяти процесса.
Параллельные запросы сериализуются через `userver::engine::Mutex`.
Перезапуск процесса сбрасывает всё состояние; внутри цепочки фаззинга
процесс перезапускать нельзя. Между независимыми сценариями используй
перезапуск или `reset`/новый `prepare`. При конкурентном запуске порядок
определяется захватом mutex; точные цепочки выше воспроизводи последовательно.

## Внешняя зависимость

Отдельный контракт сервиса зависимости — [dependency-openapi.yaml](dependency-openapi.yaml),
OpenAPI 3.0.3: `POST /decision` на порту 8081. Схема самодостаточна, без ссылок
на другие файлы: её можно отдельно передавать инструментам генерации моков.
Вход — `{"mode":"safe","value":10}`, нормальный ответ —
`{"decision":"accept"}` или `{"decision":"retry"}`. Ограничения входа
согласованы со схемой основного сервиса и проверяются тестом.
Ошибочные ответы и задержки mockserver используются отдельно для fault injection.

`POST /dependency/crash` принимает те же поля `mode` (`safe` или `fast`)
и `value` (целое от 0 до 100), что `/stateless/error`. После валидации он
делает настоящий HTTP POST с тем же JSON на адрес из config var `dependency-url`.
По умолчанию это `http://127.0.0.1:8081/decision`; адрес не берётся из запроса.

Зависимость должна вернуть HTTP 200 и JSON ровно с одним полем:
`{"decision":"accept"}` или `{"decision":"retry"}`. Обычный ответ ручки —
`{"value":13,"decision":"accept"}`. Процесс падает только при совместном
выполнении трёх условий: `mode=fast`, `value=13`, ответ зависимости — `retry`.
Для `safe`, другого числа или решения `accept` ручка возвращает 200.

Сетевой сбой, таймаут, статус зависимости не 200, невалидный JSON или другая
структура ответа дают 502. Одна попытка, таймаут 500 мс, редиректы выключены.
Невалидный вход даёт 400 без вызова зависимости. Ручка не хранит состояние
и не кэширует ответы зависимости.

Для ручного воспроизведения можно запустить простую зависимость в отдельном
терминале (замени `retry` на `accept`, чтобы выключить условие падения):

```sh
python3 - <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer

class Decision(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        body = b'{"decision":"retry"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(('127.0.0.1', 8081), Decision).serve_forever()
PY
```

Затем из корня репозитория запусти сервис с обычными config vars:

```sh
./build/macos-debug/services/simple-target-service/simple_target_service \
  --config services/simple-target-service/configs/static_config.yaml \
  --config_vars services/simple-target-service/configs/config_vars.yaml
```

Запрос из третьего терминала воспроизведёт падение:

```sh
curl -X POST localhost:8080/dependency/crash \
  -H 'Content-Type: application/json' -d '{"mode":"fast","value":13}'
```

В testsuite URL подменяется на mockserver через штатный config hook.
Ответ зависимости можно менять фикстурой `decision_dependency`. Тестовый
config hook сохраняет timeout 500 мс вместо стандартных 10 секунд testsuite.
Отдельный crash-тест сначала проверяет три безопасных сочетания, затем
подтверждает `SIGABRT` при нужном запросе и ответе зависимости.

## Сборка и запуск

Команды общей сборки из корня репозитория и особенности macOS приведены
в [основном README](../../README.md).

Штатный flow шаблона из этой папки при установленных зависимостях userver:

```sh
make build-debug
make test-debug
make start-debug
```

`debug` включает ASan/UBSan. Для изменения локальных параметров предусмотрен
`CMakeUserPresets.json` с пользовательским preset `debug-custom` и команды
`make build-debug-custom`, `make test-debug-custom`, `make start-debug-custom`.
Дополнительные параметры CMake можно передать через `CMAKE_OPTS`, число задач —
через `NPROCS`.

Unit-тест и benchmark проверяют функцию приветствия. Testsuite проверяет
обычные ответы, 400/409, намеренный 500, сброс и независимость состояния,
валидность OpenAPI и соответствие ответов схемам, реальные вызовы mockserver
и ошибки внешней зависимости. Четыре crash-теста запускают
изолированные процессы и проверяют именно `SIGABRT` на допустимых по OpenAPI
входах; core dumps в этих дочерних процессах отключены.
Фаззеры пока не подключены.

В конфиге `http-client-core` включён и вне testsuite: от него зависит
`http-client`. Это позволяет запускать тот же бинарник напрямую для фаззера.

## Источники

- [Официальный flow создания сервиса](../../third_party/userver/scripts/docs/en/userver/build/build.md).
- [Устройство HTTP-сервиса](../../third_party/userver/scripts/docs/en/userver/tutorial/hello_service.md).

Сгенерированные `.github/` относятся к самостоятельному репозиторию сервиса.
Для этого монорепозитория их потребуется отдельно адаптировать перед включением CI.

## License

Исходный шаблон распространяется под
[Apache-2.0](https://github.com/userver-framework/userver/blob/v3.2/LICENSE).
