## 如何添加自定义庭院

1. 在`./tasks/Component/Costume`文件夹下面新建一个你的这个庭院皮肤文件夹比如`mainxxx`

2. 在你的文件夹下面新增一个`image.json`，启动`gui.py`对应工具添加对应的assets

   **很重要很重要，你不要乱划动庭院，如果你留意到游戏在你的停留位置是默认的**

   **在你生成之前需要点击探索然后在回来、再点击町中然后回来，确保你的当前的位置的默认的**

   你需要生成如下的assets:

   - check_main_xxx:   这张图片用来判断是否在庭院的
   - main_goto_exploration_xxx:  这张图片是用来点击"探索"图标的
   - main_goto_summon_xxx:  这张图片是用来点击 ”召唤“
   - main_goto_town_xxx:   町中知道吧
   - pet_house_xxx:  进入宠物屋

3. 执行`./dev_tools/assets_extract.py`这个将会更新`./tasks/Component/Costume/assets.py` 你不需要手动修改这个文件

4. 好了你现在以及输出你这个庭院皮肤的assets了，下面是为其加入 OAS 中

5. 打开`./tasks/Component/Costume/config.py`看到类似这种的，照着填进去

   ```python
   COSTUME_MAIN_2 = 'costume_main_2'  # 琼夜淬光
   ```

6. 打开`./tasks/Component/Costume/costume_base.py`看到类似这种的，照着填进去。

   解释一下，`COSTUME_MAIN_2` 是你刚刚定义的一个庭院类型，后面的第一个key就是原先的assets, 后面的value就是你刚刚输出的要替换的原先的assets。具体的值在`assets.py`文件有定义。照着填没毛病吧。

   ```python
   MainType.COSTUME_MAIN_2: {'I_CHECK_MAIN': 'I_CHECK_MAIN_1',
                                 'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_1',
                                 'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_1',
                                 'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_1',
                                 'I_PET_HOUSE': 'I_PET_HOUSE_1', },
   ```

7. 完事之后，你需要测试一下。执行`./tasks/Component/Costume/costume_test.py` 这个文件。

   **在测试之前你需要打开一次 OASX 修改你对应的庭院皮肤的选项**

8. 完事啦？？？哪有那么简单，你没有发现打开 OASX 的时候发现你的选项还是 `costume_main_xxx` 这种吗。你还需要添加一个翻译，[点击这儿](https://runhey.github.io/OnmyojiAutoScript-website/docs/development/user-option#7翻译)


---

## 如何添加「动态庭院」（画面会随时段变化）

有些庭院是动态的：**同一个按钮在不同时段/场景下配色和画面内容都不同**
（例：`costume_main_18` 天穹之境有 夕 / 夜 / 昼 三种画面）。这种庭院一张模板只能命中一个时段，
其他时段必然匹配失败，所以要**每个时段各裁一份**，运行时按当前画面挑一张能命中的。

参考实现：`costume_main_18`（`./tasks/Component/Costume/main18/`）。

**改动清单（照着做就行，一共 5 处）**

| # | 位置 | 改什么 |
|---|---|---|
| 1 | `tasks/Component/Costume/mainNN/` | 新建文件夹：每个功能 × 每个时段各一张 png + `image.json` |
| 2 | `tasks/Component/Costume/assets.py` | 手工加 5×N 条 `I_XXX_NN_时段` 规则（**别整文件重跑 assets_extract**，会重排） |
| 3 | `tasks/Component/Costume/config.py` | `MainType` 里加 `COSTUME_MAIN_NN = 'costume_main_NN'  # 中文名` |
| 4 | `tasks/Component/Costume/costume_base.py` | 补一行 `main_costume_model[MainType.COSTUME_MAIN_NN] = {...}`（见下面第 3 小节） |
| 5 | `assets/i18n/zh-CN.json` | 加 `"costume_main_NN": "中文名"`（Web UI 下拉显示用；Qt 的 `zh_CN.xml` 里 1~18 都没有，属既有缺口） |

改完**必须重启脚本进程**（`assets.py`/`config.py`/`costume_base.py` 都是进程启动时加载的），
Web UI 刷新浏览器即可。可选：`I_WQ_DONE_NN` / `I_HARVEST_*_NN` 这些非强制的资源，
如果该庭院的悬赏完成标记、收菜按钮位置也不一样再补（缺了会自动跳过、不影响其它功能）。

### 1. 资产命名

每个功能 × 每个时段各一张，命名 `<功能>_<编号>_<时段>`：

```
main18_check_main_18_night.png / _dusk.png / _day.png
main18_main_goto_exploration_18_night.png / _dusk.png / _day.png
main18_main_goto_summon_18_night.png / _dusk.png / _day.png
main18_main_goto_town_18_night.png / _dusk.png / _day.png
main18_pet_house_18_night.png / _dusk.png / _day.png
```

生成的常量名就是 `I_` + 大写，例如 `I_MAIN_GOTO_TOWN_18_NIGHT`。
时段名随便起（`night/dusk/day`），只要前后一致即可。

### 2. 三条硬规则

1. **所有候选必须共用同一 `roiFront` / `roiBack`**
   （实测三张图里元素位置一致，只有配色/内容不同）。
   这样即使将来出现没收录的新时段、候选全不中而回退到第一张，**点击位置依然是对的**，
   不会点到别的地方去。
2. **阈值统一 0.8**（比普通庭院常用的 0.55~0.7 严）。
   因为"选哪一套"靠的就是匹配分：跨时段误匹配分实测只有 0.15~0.66，离 0.8 很远，
   这样每个时段都能稳定选中"自己那张"。
3. **候选顺序 = 优先级**，把最独特、最不容易误命中别的时段的那张放最前
   （天穹之境是把 `night` 放最前）。

### 3. 在 `costume_base.py` 里注册成候选列表

普通庭院是「一个 key → 一个资产名」；动态庭院把需要多状态的那些 key 写成**列表**：

```python
# 动态庭院（画面随时段变）：每个按钮都给多个时段各一份候选
main_costume_model[MainType.COSTUME_MAIN_19] = {
    **_main_costume_assets(19),
    **{key: [f'{key}_19_NIGHT', f'{key}_19_DUSK', f'{key}_19_DAY']
       for key in ('I_CHECK_MAIN', 'I_MAIN_GOTO_EXPLORATION', 'I_MAIN_GOTO_SUMMON',
                   'I_MAIN_GOTO_TOWN', 'I_PET_HOUSE')},
}
```

- 只有部分功能需要多状态时，就只把那几个 key 写成列表，其余保持字符串（走原来的单模板逻辑）。
- 列表的处理在 `CostumeBase._pick_multi_state_rule()`：**按顺序试，命中第一张就用**；
  没有截图或全不中时用第一张兜底。
- 注意 `main_costume_model` 的字典推导式只到 `range(1, 18)`，**新增庭院编号要像上面这样单独补一行**
  （并把 `config.py` 的枚举、两套 i18n 一起补上，见上面第 5、8 步）。
