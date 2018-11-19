import datetime
import json
import rethinkdb as r
from tornado import ioloop

RDB_HOST = 'localhost'
RDB_PORT = 28015
RDB_NAME = 'iOSTest'


def time_now():
    return datetime.datetime.now(r.make_timezone('+08:00'))


def setup():
    conn = r.connect(RDB_HOST, RDB_PORT)

    def safe_run(rql):
        try:
            return rql.run(conn)
        except r.RqlRuntimeError:
            return False

    print("database init db and tables")
    safe_run(r.db_create(RDB_NAME))
    safe_run(r.db(RDB_NAME).table_create("tasks", primary_key='id'))
    safe_run(r.db(RDB_NAME).table_create('devices', primary_key='id'))
    print("database init done")
    conn.close()

    r.set_loop_type('tornado')


class DB(object):
    def __init__(self, host='localhost', port=28015, db='iOSTest'):
        self._host = host
        self._port = port
        self._db = db

    async def run(self, resql):
        conn = await r.connect(self._host, self._port, self._db)
        try:
            return await resql.run(conn)
        finally:
            conn.close()

    async def update_or_insert(self,
                               table_name: str,
                               data: dict,
                               primary_key='id') -> (str, bool):
        """
        Return:
            (id, inserted)
        """
        if primary_key != 'id':
            assert primary_key in data

        # update first
        if primary_key in data:
            id = data[primary_key]
            ret = await self.run(r.table(table_name).get(id).update(data))
            if not ret['skipped']:
                return id, False

        # insert data into table
        data["createdAt"] = time_now()
        ret = await self.run(r.table(table_name).insert(data))
        assert ret['errors'] == 0

        # get id
        if "generated_keys" in ret:
            return ret["generated_keys"][0], True
        return data[primary_key], False

    async def task_save(self, task: dict) -> str:
        """
        Save task into db

        Returns:
            saved task id
        """
        task_id, _ = await self.update_or_insert("tasks", task)
        return task_id

    async def device_save(self, device: dict, primary_key='id'):
        if primary_key in device:
            id = device[primary_key]
            ret = await self.run(r.table('devices').get(id).update(device))
        await self.run(r.table('devices').insert(device))
        assert ret['errors'] == 0

    async def _get_all(self, table_name: str, filter=None):
        """
        Args:
            filter: rethinkdb filter or function return resql

        Return
            Async Generator

        Required Python 3.6
        """
        resql = r.table(table_name)
        if callable(filter):
            resql = filter(resql)
        elif filter:
            resql = resql.filter(filter)
        conn = await r.connect(self._host, self._port, self._db)
        try:
            cursor = await resql.run(conn)
            while (await cursor.fetch_next()):
                item = await cursor.next()
                yield item
        finally:
            conn.close()

    async def task_all(self, filter=None):
        """
        Return
            Async Generator

        Required Python 3.6
        """
        return await self.run(
            r.table("tasks").order_by(r.desc("createdAt")))

    def device_all(self, filter=None):
        return self._get_all('devices', filter)


db = DB(RDB_HOST, RDB_PORT, RDB_NAME)
