# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.base.timer import Timer
from module.exception import RequestHumanTakeover, GameTooManyClickError, GameStuckError
from module.logger import logger
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.chess_battle import ChessBattleNavigationMixin
from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask


class LoginService(
    ChessBattleNavigationMixin,
    BaseTask,
    RestartAssets,
    GameUiAssets,
):
    character: str
    # OCR 识别不到"进入"两个字时, 兜底点击"进入游戏"区域中心的最大次数
    ENTER_GAME_FALLBACK_MAX: int = 5
    # 兜底点击的间隔(秒)。需要大于 OCR 的点击间隔(3秒), 让 OCR 优先生效
    ENTER_GAME_FALLBACK_INTERVAL: float = 5

    def __init__(self, *wargs, **kwargs):
        super().__init__(*wargs, **kwargs)
        self.character = self.config.restart.login_character_config.character
        self.O_LOGIN_SPECIFIC_SERVE.keyword = self.character
        self.enter_game_fallback_count = 0
        self.enter_game_fallback_timer = Timer(self.ENTER_GAME_FALLBACK_INTERVAL)

    def _app_handle_login(self) -> bool:
        """
        最终是在庭院界面
        :return:
        """
        logger.hr('App login')
        self.device.stuck_record_add('LOGIN_CHECK')

        confirm_timer = Timer(1.5, count=2).start()
        orientation_timer = Timer(10)
        skip_login_animation = True
        skip_click_mx_cnt = 5
        login_success = False
        # 每次登录重新计数, 避免上一次的兜底次数残留
        self.enter_game_fallback_count = 0
        self.enter_game_fallback_timer = Timer(self.ENTER_GAME_FALLBACK_INTERVAL).start()

        while 1:
            if not login_success and orientation_timer.reached():
                self.device.get_orientation()
                orientation_timer.reset()

            self.screenshot()
            if self.appear_then_click(
                self.I_RETURN_CHESS_CANCEL,
                interval=0.8,
            ):
                logger.info(
                    'Cancel returning to interrupted Chess battle; '
                    'wait for result flow'
                )
                continue
            if self.appear(self.I_CHECK_CHESS):
                logger.info(
                    'Login recovery reached Chess lobby; '
                    'finish recovery without returning to courtyard'
                )
                return True
            if self.chess_result_flow_visible():
                logger.info(
                    'Login recovery detected unfinished Chess result flow'
                )
                self.return_to_chess_lobby()
                return True
            if self.appear_then_click(self.I_CANCEL_BATTLE, interval=0.8):
                logger.info('Cancel continue battle')
                continue
            if self.appear(self.I_CHECK_MAIN, interval=0.2) and not self.appear(self.I_MAIN_GOTO_SHIKIGAMI_RECORDS):
                logger.info('The main had already appeared, but shikigami records had not yet appeared')
                skip_login_animation = False
                if self.click(self.C_LOGIN_SCROLL_CLOSE_AREA, interval=2):
                    continue
            if self.appear(self.I_MAIN_GOTO_SHIKIGAMI_RECORDS, interval=0.2):
                if confirm_timer.reached():
                    logger.info('Login to main confirm (shikigami records button appears)')
                    break
            else:
                confirm_timer.reset()
            if self.appear(self.I_MAIN_GOTO_SHIKIGAMI_RECORDS, interval=0.5):
                logger.info('Login success: shikigami records button appears')
                login_success = True
                skip_login_animation = False
            if self.appear(self.I_HARVEST_ZIDU, interval=1):
                self.I_HARVEST_ZIDU.roi_front[0] -= 200
                self.I_HARVEST_ZIDU.roi_front[1] -= 200
                if self.click(self.I_HARVEST_ZIDU, interval=2):
                    logger.info('Close zidu')
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=2.5):
                logger.info('Soul overflow confirm')
                continue
            if self.appear_then_click(self.I_LOGIN_LOAD_DOWN, interval=1):
                logger.info('Download inbetweening')
                continue
            if self.appear_then_click(self.I_WATCH_VIDEO_CANCEL, interval=0.6):
                logger.info('Close video')
                continue
            if self.appear_then_click(self.I_LOGIN_RED_CLOSE, interval=0.6):
                logger.info('Close red close')
                continue
            if self.appear_then_click(self.I_LOGIN_YELLOW_CLOSE, interval=0.6):
                logger.info('Close yellow close')
                continue
            if self.appear_then_click(self.I_LOGIN_LOGIN_GOTO_BIND_PHONE):
                while 1:
                    self.screenshot()
                    if self.appear_then_click(self.I_LOGIN_LOGIN_CANCEL_BIND_PHONE):
                        logger.info("Close bind phone")
                        break
                continue
            from tasks.Component.GeneralInvite.assets import GeneralInviteAssets as gia
            if self.appear_then_click(gia.I_I_REJECT, interval=0.8):
                logger.info("reject invites")
                continue
            if self.appear_then_click(self.I_LOGIN_LOGIN_ONMYOJI_GENIE):
                logger.info("click onmyoji genie")
                continue
            if self.appear(self.I_LOGIN_SPECIFIC_SERVE, interval=0.6) \
                    and self.ocr_appear_click(self.O_LOGIN_SPECIFIC_SERVE, interval=0.6):
                while True:
                    self.screenshot()
                    if self.appear(self.I_LOGIN_SPECIFIC_SERVE):
                        self.click(self.C_LOGIN_ENSURE_LOGIN_CHARACTER_IN_SAME_SVR, interval=2)
                        continue
                    break
                logger.info('login specific user')
                continue

            if self.appear(self.I_CREATE_ACCOUNT):
                logger.warning('Appear create account')
                raise GameStuckError('Appear create account')
            if self.appear(self.I_CHARACTARS, interval=1):
                logger.info('误入区服设置')
                self.device.click(x=106, y=535)
                continue
            if self.appear(self.I_EARLY_SERVER) and self.appear_then_click(self.I_EARLY_SERVER_CANCEL):
                logger.info('Cancel switch from early server to normal server')
                continue

            # 进入登录页面后或点击超过一定次数不再处理登录动画逻辑
            if self.appear(self.I_LOGIN_8, interval=0.6) or skip_click_mx_cnt <= 0:
                skip_login_animation = False
            if skip_login_animation:
                if self.ocr_appear_click(self.O_LOGIN_ANIMATION_SKIP, interval=2.5):  # 点击跳过登录动画
                    continue
                if self.click(self.C_LOGIN_ANIMATION_CENTER, interval=5):  # 点击屏幕中央触发跳过显示
                    skip_click_mx_cnt -= 1

            if self.login_enter_game():
                skip_login_animation = False  # 进入登录页面后不再处理登录动画逻辑
                self.wait_until_appear(self.I_LOGIN_SPECIFIC_SERVE, True, wait_time=5)
                continue

        return login_success

    def login_enter_game(self) -> bool:
        """
        点击进入游戏按钮
        OCR 能识别到"进入"时点击识别到的位置;
        识别不到(字体/描边/动画等原因)时, 兜底点击 "进入游戏" OCR 区域的中心位置, 避免一直卡在登录首页
        :return: 是否执行了点击
        """
        if self.ocr_appear_click(self.O_LOGIN_ENTER_GAME, interval=3):
            self.enter_game_fallback_count = 0
            return True
        # 兜底次数已经用尽, 不再盲点
        if self.enter_game_fallback_count >= self.ENTER_GAME_FALLBACK_MAX:
            return False
        # 只在登录首页(出现登录选区标志)兜底, 防止在角色选择等其它界面点错地方
        if not self.appear(self.I_LOGIN_8):
            return False
        if not self.enter_game_fallback_timer.reached():
            return False
        self.enter_game_fallback_timer.reset()
        self.enter_game_fallback_count += 1
        x, y, w, h = self.O_LOGIN_ENTER_GAME.roi
        x, y = int(x + w / 2), int(y + h / 2)
        logger.warning(
            f'OCR "进入" not found, click enter game area center ({x}, {y}), '
            f'{self.enter_game_fallback_count}/{self.ENTER_GAME_FALLBACK_MAX}')
        self.device.click(x=x, y=y, control_name='login_enter_game_center')
        if self.enter_game_fallback_count >= self.ENTER_GAME_FALLBACK_MAX:
            # 防止与主循环中其它点击叠加触发 GameTooManyClickError
            self.device.click_record_clear()
        return True

    def app_handle_login(self) -> bool:
        self.device.stuck_record_clear()
        self.device.click_record_clear()
        try:
            self._app_handle_login()
            return True
        except (GameTooManyClickError, GameStuckError) as e:
            logger.warning(e)
            self.device.app_stop()
            self.device.app_start()

        logger.critical('Login failed')
        logger.critical('Onmyoji server may be under maintenance, or you may lost network connection')
        raise RequestHumanTakeover

    def set_specific_usr(self, character: str):
        self.character = character
        self.O_LOGIN_SPECIFIC_SERVE.keyword = character
