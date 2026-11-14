from module.exception import TaskEnd
import tasks.GameUi.page as pages
from tasks.GameUi.game_ui import GameUi
from tasks.MetaDemonTicket.ticket_farming import run_ticket_farming


class ScriptTask(GameUi):
    def run(self):
        meta = self.config.meta_demon_ticket
        full = run_ticket_farming(self, meta.general_config.mode)
        self.set_next_run(task='MetaDemonTicket', success=full)
        if meta.general_config.realm_raid_enable:
            self.config.task_call('RealmRaid')
        self.goto_page(pages.page_main)
        raise TaskEnd
