# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from time import sleep
from datetime import time, datetime, timedelta

from module.logger import logger
from module.exception import TaskEnd


from tasks.RichMan.assets import RichManAssets
from tasks.RichMan.config import RichMan
from tasks.RichMan.mall.mall import Mall
from tasks.RichMan.guild import Guild
from tasks.RichMan.shrine import Shrine
from tasks.RichMan.thousand_things import ThousandThings


class ScriptTask(Mall, Guild, ThousandThings, Shrine):

    def run(self):
        con: RichMan = self.config.rich_man
        # 读取本周已完成的步骤，报错重跑时从这里接着做
        self.init_progress()
        # 千物宝箱
        self.run_step('thousand_things', lambda: self.execute_tt(con.thousand_things))
        # 神龛
        self.run_step('shrine', lambda: self.execute_shrine(con.shrine))
        # 功勋商店
        self.run_step('guild_store', lambda: self.execute_guild(con.guild_store))
        # 商店
        self.run_step('mall', lambda: self.execute_mall())

        # 原顺序执行（无进度记录），保留备查：
        # self.execute_tt(con.thousand_things)
        # self.execute_shrine(con.shrine)
        # self.execute_guild(con.guild_store)
        # self.execute_mall()

        self.set_next_run(task='RichMan', success=True, finish=False)
        raise TaskEnd('RichMan')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
    # t.execute_mall()



