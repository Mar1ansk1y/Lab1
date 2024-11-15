# Введение
Демо: https://drive.google.com/drive/folders/1KgZuLt-7h3Jd3YZJ8L3P-w3Fkg4bYC7e?usp=sharing

Для развертывания стенда использовался Debian 12.8 и lxc контейнеры в качестве Primary и StandBy серверов, так как для развертывания полноценных виртуальных машин не достаточно оперативной памяти.

|Сервер |   IP-адрес     |
|-------|----------------|
|Хост   | 192.168.56.2   |
|Primary| 192.168.56.101 |
|StandBy| 192.168.56.102 |

# Настройка PostgreSQL
Данную настройку выполняем и на Primary, и на StandBy. Для экономии времени, можно сначала настроить один из серверов, а после скопировать контейнер с помощью `lxc-copy`.
```
sudo apt install gnupg2 git gcc make flex bison libreadline-dev zlib1g-dev libpq-dev
git clone https://github.com/postgres/postgres.git && cd postgres/
git checkout REL_14_STABLE
./configure --prefix=$HOME/project
time make -j8 -s
make install 

```

# Настройка Primary

Переходим в каталог со всеми утилитами.

```
cd ~/project/bin
```

1. Создаем пустой кластер.

```
./initdb ~/db
```
2. Настройка ~/db/postgresql.conf. Сокет для подключения к БД находится в директории /tmp (по умолчанию).

```
listen_addresses = '*'
port = 5432

full_page_writes = on
wal_log_hints = on
```
3. Настройка ~/db/pg_hba.conf. Добавляем в конец следующие строки.
```
host    all             kronos          192.168.1.0/24          trust
host    replication     repuser         192.168.1.0/24          trust
```
4. Запуск кластера.
```
./pg_ctl -D ~/db start
```
5. Создаём пользователя для подключения и работы с БД kronos (-s права суперпользователя) и для репликации repuser (-c 10 максимальное кол-во подключений).
```
./createuser -P -s -h /tmp kronos
./createuser -U kronos -P -c 10 --replication -h /tmp repuser
```
6. Создаём базу данных с названием testdb.
```
./createdb --owner=kronos -h /tmp testdb
```
7. Проводим дополнительную настройку базы данных.
```
./psql -h /tmp --dbname=testdb -c "ALTER SYSTEM SET synchronous_standby_names to '*'"
./psql -h /tmp --dbname=testdb -c "SELECT pg_reload_conf();"
./psql -h /tmp --dbname=testdb -c "SET synchronous_commit to on;"
```
# Настройка StandBy
```
./pg_basebackup -h 192.168.56.101 -U repuser --create-slot --slot=rep102 --write-recovery-conf -D ~/db
```
