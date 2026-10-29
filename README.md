# userver-fuzzing

Проект по grey-box фаззингу REST- и gRPC-сервисов на C++-фреймворке
[userver](https://userver.tech/). Цель — дать разработчику удобный Python-интерфейс
в testsuite для поиска ошибок с обратной связью от работающего сервиса.

Сейчас подготовлены тестовые стенды с известными дефектами. Ближайший этап —
прогнать на них существующие фаззеры, сравнить возможности и ограничения,
а затем определить архитектуру собственного инструмента.

## Что уже есть

| Стенд | API по умолчанию | Контракт |
| --- | --- | --- |
| [REST](services/simple-target-service/README.md) | HTTP, порт 8080 | [OpenAPI](services/simple-target-service/openapi.yaml) |
| [gRPC](services/simple-grpc-target-service/README.md) | Unary gRPC, порт 8083 | [Protobuf](services/simple-grpc-target-service/proto/fuzzing/targets.proto) |

Оба стенда содержат одни и те же сценарии:

- падение процесса на определённом запросе без состояния;
- HTTP 500 или gRPC `INTERNAL` при живом процессе;
- падение после последовательности вызовов одной операции;
- падение после цепочки двух операций с общим состоянием;
- падение при сочетании запроса и ответа внешней зависимости.

Есть функциональные тесты через testsuite, моки зависимостей и проверки
воспроизведения сбоев. Падения проверяются в отдельных процессах по `SIGABRT`.
Контрольные входы, команды запуска и примеры зависимостей описаны в README
каждого стенда. Прогоны фаззеров и измерения пока не выполнены.

## Сборка и тесты

Нужны Git, CMake >= 3.24, Ninja, компилятор C++20, Python и
[зависимости userver для своей ОС](third_party/userver/scripts/docs/en/userver/build/dependencies.md).
Userver v3.2 находится в submodule `third_party/userver` и собирается из
исходников вместе со стендами.

Перед первой сборкой:

```sh
git submodule update --init --recursive
```

На Linux:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 6
ctest --preset debug
```

На macOS нужны Python 3.11 и OpenSSL 3:

```sh
cmake --preset macos-grpc-debug -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)"
cmake --build --preset macos-grpc-debug --parallel 6
ctest --preset macos-grpc-debug
```

Профиль ожидает `python3.11` в PATH. Другой путь можно передать при конфигурации
через `-DUSERVER_PYTHON_PATH=/path/to/python3.11`. Подробности macOS-сборки
и запуск через Dev Container — в [инструкции gRPC-стенда](services/simple-grpc-target-service/README.md).

Корневые presets собирают оба сервиса, их unit-тесты и benchmarks, а CTest
запускает все проверки. Число параллельных задач выбирай под ресурсы машины.
Артефакты сборки и Python-окружения находятся в `build/`.

Проверено на macOS ARM64: CTest — 6/6, функциональные проверки — 60 REST и
40 gRPC. Полный Linux-прогон пока не выполнен.

## Ближайшие планы

1. Подключить готовые REST- и gRPC-фаззеры и проверить обнаружение известных
   сбоев, включая цепочки запросов.
2. Организовать воспроизводимые эксперименты: одинаковые бюджеты, сброс
   состояния, сохранение и повторение найденных примеров.
3. Проверить сбор покрытия C++ и интеграцию с testsuite; по результатам
   выбрать основу собственного grey-box инструмента.

Подробная постановка и исследовательские вопросы — в [PROJECT.md](PROJECT.md).
