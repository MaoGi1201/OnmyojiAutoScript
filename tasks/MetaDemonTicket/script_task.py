from module.exception import TaskEnd
import tasks.GameUi.page as pages
from tasks.GameUi.game_ui import GameUi
from tasks.MetaDemonTicket.ticket_farming import run_ticket_farming


class ScriptTask(GameUi):
    def run(self):
        mode = self.config.meta_demon_ticket.general_config.mode
        full = run_ticket_farming(self, mode)
        self.set_next_run(task='MetaDemonTicket', success=full)
        self.goto_page(pages.page_main)
        raise TaskEnd
