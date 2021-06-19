import time

from gevent.pool import Pool
from gevent import monkey

import app.models as models
from app.config import sqla
from app.config.const import *
from app.spider.dynamic.dynamic_spider import crawl_dynamic_once

monkey.patch_socket()


def create_requests_and_save_data(member_id):
    session = sqla['session']

    time_start = time.time()
    print("start to crawl user dynamic with id {}".format(member_id))

    result = []
    offset = 0
    while True:
        try:
            has_more, offset, tuples = crawl_dynamic_once(member_id, offset)
        except Exception:
            return False
        result += tuples
        if has_more == 0:
            break

    for reply_tuple in result:
        dynamic = models.UserDynamic()
        dynamic.dynamic_id = reply_tuple[0]
        dynamic.type_id = reply_tuple[1]
        dynamic.oid = reply_tuple[2]
        dynamic.status = 0
        session.add(dynamic)
        session.commit()

    time_end = time.time()
    print("finished crawl dynamics for member {}, cost {}".format(member_id, time_end - time_start))
    return True


def task(member_ids, pool_number):
    session = sqla['session']
    state = session.query(models.KvStore).filter(models.KvStore.field_name == 'state').all()

    # see if the database is inited
    if not len(state):

        session.execute("truncate table user_dynamic")

        time_start = time.time()
        print("start to crawl user dynamic...")

        pool = Pool(pool_number)
        g_result = []
        for member_id in member_ids:
            result = pool.spawn(
                create_requests_and_save_data,
                member_id=member_id,
            )
            g_result.append(result)
        pool.join()

        finished = True
        for r in g_result:
            finished = r.value & finished

        if not finished:
            return

        time_end = time.time()
        print('time cost', time_end - time_start, 's')
        # set the state to already inited
        kv_entry = models.KvStore()
        kv_entry.field_name = STATE_FIELD_NAME
        kv_entry.field_value = STATE_FIELD_STARTED_VALUE
        session.add(kv_entry)
        session.commit()
