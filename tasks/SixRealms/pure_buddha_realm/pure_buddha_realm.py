import time

from module.atom.image import RuleImage
from module.exception import TaskEnd
from module.logger import logger
from tasks.SixRealms.pure_buddha_realm.base_pure_buddha_realm import BasePureBuddhaRealm
import tasks.SixRealms.pure_buddha_realm.page as pages
from typing import Callable


class PureBuddhaRealm(BasePureBuddhaRealm):

    def _default_detect_categories(self) -> set[str]:
        categories = super()._default_detect_categories()
        categories.add("six_realms")
        categories.add("pure_buddha_realm")
        return categories

    @property
    def pb_page_handle_dict(self) -> dict[pages.Page, Callable]:
        return {
            pages.page_pure_buddha_realm: self.run_on_pb,
            pages.page_pb_prepare: lambda : self.goto_page(pages.page_pb_main),
            pages.page_pb_main: self.run_on_pb_main,
            pages.page_pb_shop_land: self.run_on_pb_store,
            pages.page_pb_mistery_land: lambda : self.goto_page(pages.page_pb_main),
            pages.page_pb_chaos_land: self.run_on_pb_chaos,
            pages.page_pb_bloom_land: self.run_on_pb_refine,
            pages.page_pb_battle_land: self.run_on_pb_battle,
            pages.page_pb_challenge: self.run_on_pb_challenge,
            pages.page_pb_map: lambda: self.goto_page(pages.page_pb_main),
            pages.page_pb_exit: lambda: self.click(pages.random_click(ltrb=(True, False, False, False)), interval=1.2),
            pages.page_sr_prepare_exit: lambda: self.goto_page(pages.page_pb_prepare),
            pages.page_sr_open_store: lambda: self.goto_page(pages.page_pb_main),
            pages.page_battle_prepare: self.run_on_pb_challenge,
            pages.page_battle: self.run_on_pb_challenge,
            pages.page_battle_result: self.run_on_pb_challenge,
            pages.page_reward: lambda: self.click(pages.random_click(), interval=1.2),
        }

    def run(self):
        self.before_run()
        logger.hr('Pure Buddha Realm', 1)
        while True:
            self.screenshot()
            # 跳过过场动画 / 带「非表示」的确认框, 都先处理掉再判页面
            if self.handle_six_realms_popup():
                continue
            current_page = self.get_current_page()
            if current_page is None:
                time.sleep(0.5)
                continue
            handle = self.pb_page_handle_dict.get(current_page, None)
            if handle is None:
                self.goto_page(pages.page_pure_buddha_realm)
                continue
            try:
                handle()
            except TaskEnd:
                break
        logger.info('Pure Buddha Realm task ended')

    def run_on_pb(self):
        """净佛刹界面"""
        if self.appear_then_click(self.I_PB_CONTINUE, interval=1):
            return
        if self.appear_then_click(self.I_PB_START, interval=1):
            return

    def run_on_pb_prepare(self):
        """准备流程: 阵容确认 -> 法器秘宝(左1) -> 开局技能(右1)"""
        if self.appear_then_click(self.I_PB_START_CONFIRM, interval=1.5) or \
                self.appear_then_click(self.I_PB_START_CONFIRM2, interval=1.5) or \
                self.appear_then_click(self.I_PB_START_THIRD_SKILL, interval=1.5) or \
                self.appear_then_click(self.I_PB_SELECT_3, interval=1.5):
            return

    def run_on_pb_main(self):
        """净佛刹主界面 执行策略选岛屿"""
        if self.appear(self.I_PB_BOSS_PREPARE) and \
                self.enter_battle(self.I_PB_BOSS_FIRE, boss_unlock=self.I_PB_BOSS_UNLOCK, boss_lock=self.I_PB_BOSS_LOCK):
            logger.info('Start boss battle')
            self.run_general_battle(battle_key='boss', exit_matcher=pages.page_pure_buddha_realm)
            raise TaskEnd
        # 优先级：神秘 > 練磨 > 激戦 > 安息 > 混沌
        islands = [self.I_PB_LAND_MYSTERY, self.I_PB_LAND_BLOOM, self.I_PB_LAND_FIRE, self.I_PB_LAND_STORE,
                   self.I_PB_LAND_CHAOS]
        self.choose_and_enter_island(islands)

    def run_on_pb_challenge(self):
        """净佛刹挑战界面"""
        if self.enter_battle(self.I_PB_BATTLE_FIRE):
            self.run_general_battle(battle_key="normal", exit_matcher=pages.page_pb_main)

    def run_on_pb_store(self):
        """安息之岛: 右下角返回"""
        logger.hr('rest land')
        self.appear_then_click(self.I_PB_STORE_EXIT, interval=1.5)

    def run_on_pb_refine(self):
        """練磨之岛: 右下角返回"""
        logger.hr('refine land')
        self.appear_then_click(self.I_PB_BLOOM_EXIT, interval=1.5)

    def run_on_pb_chaos(self):
        """混沌之屿 宝箱/精英"""
        logger.hr('chaos land')
        is_box: bool = self.appear(self.I_PB_CHAOS_BOX)
        if is_box:
            logger.info('Do not get box')
            self.appear_then_click(self.I_PB_CHAOS_EXIT, interval=1.5)
            return
        self.ui_click(self.C_NPC_FIRE_CENTER, self.I_PB_BATTLE_FIRE, interval=0.8)
        if self.enter_battle(self.I_PB_BATTLE_FIRE):
            logger.info('Start elite battle')
            self.run_general_battle(battle_key="elite", exit_matcher=pages.page_pb_main)

    def run_on_pb_battle(self):
        """激戦之屿 普通怪"""
        logger.hr('fire land')
        self.ui_click(self.C_NPC_FIRE_RIGHT, self.I_PB_BATTLE_FIRE, interval=0.8)
        if self.enter_battle(self.I_PB_BATTLE_FIRE):
            logger.info('Start normal battle')
            self.run_general_battle(battle_key="normal", exit_matcher=pages.page_pb_main)
