# This Python file uses the following encoding: utf-8
# @author AzurTian
from tasks.ActivityShikigami.activities.direct import DirectClimbAct
from tasks.base_task import BaseTask


class ScriptTask(BaseTask):
    """活动爬塔入口。

    入口形态不在配置里暴露 —— 一期活动只会用到一种，需要切换时直接改下面实例化的类：

        DirectClimbAct  四入口各自直达（100体 / 体力 / 门票 / boss 各一个按钮）
        NormalClimbAct  三入口，ap 与 pass 共用入口，靠 I_CLIMB_MODE_SWITCH 切换

    两者的到达层与战斗层完全共用，差别只在 `ENTRY_GROUPS` 的分组方式。
    """

    def run(self):
        DirectClimbAct(self.config, self.device).run()


if __name__ == '__main__':
    print([1, 2, 3][2])
