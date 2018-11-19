# coding: utf-8

import rethinkdb as r
from rethinkdb.errors import RqlRuntimeError, RqlDriverError
import os


RDB_HOST =  os.environ.get('RDB_HOST') or 'localhost'
RDB_PORT = os.environ.get('RDB_PORT') or 28015
RDB_DBNAME = os.environ.get("RDB_DBNAME") or "iOSTester"

def init_db():
    conn = r.connect(RDB_HOST, RDB_PORT)
    try:
        r.db_create(RDB_DBNAME).run(conn)
        r.db(RDB_DBNAME).table_create("devices").run(conn)
        print("App database created")
    except (RqlRuntimeError, RqlDriverError) as e:
        print("App already exists")

init_db()

def db_run(rsql):
    try:
        c = r.connect(RDB_HOST, RDB_PORT, db=RDB_DBNAME)
        return rsql.run(c)
    except RqlDriverError:
        print("No database connection chould be established")


def device_save(id :str, v: dict):
    ret = db_run(r.table("devices").get(id).update(v))
    print(ret)
    if ret['skipped']:
        v['id'] = id
        db_run(r.table("devices").insert(v))


def device_reset():
    db_run(r.table("devices").update({"status": "offline"}))