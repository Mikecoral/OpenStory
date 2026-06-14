# 复兴大观园·剧情模式 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `examples/story/` 创建剧情模式"复兴大观园"——玩家选定一个红楼梦人物，扮演该角色带领大观园走向复兴（稳定度从50升至100），若稳定度跌至0则失败。

**Architecture:** 项目基于 `examples/story_of_the_stone` 架构（Ray分布式、Redis存储、插件化Agent），核心新增：① 角色选择界面；② 全局稳定度分数（Redis key `story:score`）由 ReflectPlugin 每 tick LLM 判断 ±10；③ 玩家只能对自己的角色"下达任务"，不能干预其他 NPC；④ run_simulation.py 每 tick 后检测胜负并广播结果。

**Tech Stack:** Python/asyncio, Ray, Redis, FastAPI, Vanilla JS, HTML/CSS, TMX地图, DeepSeek API (OpenAI-compatible)

---

## 文件结构

```
examples/story/
├── run_simulation.py               [新建] 项目入口，基于deduction改造，增加胜负检测
├── BasicController.py              [复制] 同deduction
├── BasicPodManager.py              [复制] 同deduction
├── registry.py                     [新建] 注册StoryAgent资源
├── frontend/
│   ├── character_select.html       [新建] 角色选择界面（独立页面）
│   ├── character_select.js         [新建] 角色选择逻辑
│   ├── character_select.css        [新建] 角色选择样式
│   ├── index.html                  [新建] 主游戏UI（基于deduction改造）
│   ├── app.js                      [新建] 主游戏逻辑（基于deduction改造）
│   ├── style.css                   [新建] 样式（基于deduction改造）
│   └── i18n.js                     [复制] 同deduction
├── configs/
│   ├── simulation_config.yaml      [新建] 主配置
│   ├── system_config.yaml          [复制] 同deduction
│   ├── agents_config.yaml          [新建] StoryAgent模板
│   ├── models_config.yaml          [复制] 同deduction
│   ├── actions_config.yaml         [复制] 同deduction
│   ├── environment_config.yaml     [复制] 同deduction
│   └── db_config.yaml              [复制] 同deduction
├── plugins/
│   ├── agent/
│   │   ├── perceive/BasicPerceivePlugin.py   [复制] 同deduction
│   │   ├── plan/BasicPlanPlugin.py           [复制] 同deduction
│   │   ├── invoke/BasicInvokePlugin.py       [新建] 限制user_plan仅对玩家角色有效
│   │   ├── reflect/BasicReflectPlugin.py     [新建] 增加分数评估逻辑（核心改动）
│   │   ├── state/BasicStatePlugin.py         [复制] 同deduction
│   │   └── profile/BasicProfilePlugin.py     [复制] 同deduction（若存在）
│   ├── action/                               [复制] 同deduction
│   ├── environment/                          [复制] 同deduction
│   └── utils/                               [复制] 同deduction
└── data/
    ├── characters.json             [新建] 角色选择界面数据（27角色+孙悟空）
    ├── agents/
    │   ├── profiles.jsonl          [新建] 同deduction profiles_test.jsonl（复制+扩展）
    │   └── states.jsonl            [复制] 同deduction
    └── relations/
        └── relations.jsonl         [复制] 同deduction
```

---

## Task 1: 项目目录与配置文件搭建

**Files:**
- Create: `examples/story/` (整个目录结构)
- Create: `examples/story/configs/simulation_config.yaml`
- Create: `examples/story/registry.py`
- Copy: 所有configs, plugins, data（见下）

- [ ] **Step 1: 复制基础目录结构**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory

# 创建目录
mkdir -p examples/story/frontend
mkdir -p examples/story/configs
mkdir -p examples/story/plugins/agent/perceive
mkdir -p examples/story/plugins/agent/plan
mkdir -p examples/story/plugins/agent/invoke
mkdir -p examples/story/plugins/agent/reflect
mkdir -p examples/story/plugins/agent/state
mkdir -p examples/story/plugins/agent/profile
mkdir -p examples/story/plugins/action/move
mkdir -p examples/story/plugins/action/communication
mkdir -p examples/story/plugins/action/other
mkdir -p examples/story/plugins/environment/relation
mkdir -p examples/story/plugins/utils
mkdir -p examples/story/data/agents
mkdir -p examples/story/data/relations

# 复制配置文件
cp examples/story_of_the_stone/configs/system_config.yaml examples/story/configs/
cp examples/story_of_the_stone/configs/models_config.yaml examples/story/configs/
cp examples/story_of_the_stone/configs/actions_config.yaml examples/story/configs/
cp examples/story_of_the_stone/configs/environment_config.yaml examples/story/configs/
cp examples/story_of_the_stone/configs/db_config.yaml examples/story/configs/

# 复制插件
cp examples/story_of_the_stone/plugins/agent/perceive/BasicPerceivePlugin.py examples/story/plugins/agent/perceive/
cp examples/story_of_the_stone/plugins/agent/perceive/__init__.py examples/story/plugins/agent/perceive/ 2>/dev/null || touch examples/story/plugins/agent/perceive/__init__.py
cp examples/story_of_the_stone/plugins/agent/plan/BasicPlanPlugin.py examples/story/plugins/agent/plan/
cp examples/story_of_the_stone/plugins/agent/plan/__init__.py examples/story/plugins/agent/plan/ 2>/dev/null || touch examples/story/plugins/agent/plan/__init__.py
cp examples/story_of_the_stone/plugins/agent/state/BasicStatePlugin.py examples/story/plugins/agent/state/
cp examples/story_of_the_stone/plugins/agent/state/__init__.py examples/story/plugins/agent/state/ 2>/dev/null || touch examples/story/plugins/agent/state/__init__.py

# 复制 action / environment / utils 插件
cp -r examples/story_of_the_stone/plugins/action/ examples/story/plugins/action/
cp -r examples/story_of_the_stone/plugins/environment/ examples/story/plugins/environment/
cp -r examples/story_of_the_stone/plugins/utils/ examples/story/plugins/utils/

# 复制 __init__.py
find examples/story_of_the_stone/plugins -name "__init__.py" | while read f; do
  target="${f/deduction/story}"
  mkdir -p "$(dirname $target)"
  cp "$f" "$target"
done

# 复制数据
cp examples/story_of_the_stone/data/agents/profiles_test.jsonl examples/story/data/agents/profiles.jsonl
cp examples/story_of_the_stone/data/agents/states.jsonl examples/story/data/agents/
cp examples/story_of_the_stone/data/relations/relations.jsonl examples/story/data/relations/

# 复制 map 目录（软链接，避免重复存储大文件）
ln -sf "$(pwd)/examples/story_of_the_stone/map" examples/story/map

# 复制 i18n
cp examples/story_of_the_stone/frontend/i18n.js examples/story/frontend/

# 复制 BasicController, BasicPodManager
cp examples/story_of_the_stone/BasicController.py examples/story/
cp examples/story_of_the_stone/BasicPodManager.py examples/story/

echo "Done"
```

Expected output: `Done`

- [ ] **Step 2: 创建 `__init__.py` 文件**

```bash
touch examples/story/__init__.py
touch examples/story/plugins/__init__.py
touch examples/story/plugins/agent/__init__.py
touch examples/story/plugins/agent/invoke/__init__.py
touch examples/story/plugins/agent/reflect/__init__.py
touch examples/story/plugins/agent/profile/__init__.py
```

- [ ] **Step 3: 创建 `configs/simulation_config.yaml`**

文件内容（`examples/story/configs/simulation_config.yaml`）：
```yaml
simulation:
  max_ticks: 120   # 10天 × 12tick/天

api_server:
  host: "0.0.0.0"
  port: 8001        # 与deduction区分，使用8001端口

pod:
  pod_size: 5

agent_template: "StoryAgent"

db: !include db_config.yaml
system: !include system_config.yaml
agents: !include agents_config.yaml
actions: !include actions_config.yaml
environment: !include environment_config.yaml
```

- [ ] **Step 4: 创建 `configs/agents_config.yaml`**

文件内容（`examples/story/configs/agents_config.yaml`）：
```yaml
agents:
  - name: StoryAgent
    component_order:
      - perceive
      - plan
      - invoke
      - state
      - reflect
    components:
      perceive:
        plugin: BasicPerceivePlugin
        module: examples.story.plugins.agent.perceive.BasicPerceivePlugin
      plan:
        plugin: BasicPlanPlugin
        module: examples.story.plugins.agent.plan.BasicPlanPlugin
      invoke:
        plugin: BasicInvokePlugin
        module: examples.story.plugins.agent.invoke.BasicInvokePlugin
        adapters:
          redis: RedisKVAdapter
      state:
        plugin: BasicStatePlugin
        module: examples.story.plugins.agent.state.BasicStatePlugin
        adapters:
          redis: RedisKVAdapter
      reflect:
        plugin: BasicReflectPlugin
        module: examples.story.plugins.agent.reflect.BasicReflectPlugin
```

- [ ] **Step 5: 创建 `registry.py`**

文件内容（`examples/story/registry.py`）：
```python
from examples.story.plugins.agent.perceive.BasicPerceivePlugin import BasicPerceivePlugin
from examples.story.plugins.agent.plan.BasicPlanPlugin import BasicPlanPlugin
from examples.story.plugins.agent.invoke.BasicInvokePlugin import BasicInvokePlugin
from examples.story.plugins.agent.state.BasicStatePlugin import BasicStatePlugin
from examples.story.plugins.agent.reflect.BasicReflectPlugin import BasicReflectPlugin
from examples.story.plugins.action.move.BasicMovePlugin import BasicMovePlugin
from examples.story.plugins.action.communication.BasicCommunicationPlugin import BasicCommunicationPlugin
from examples.story.plugins.action.other.BasicOtherActionPlugin import BasicOtherActionPlugin
from examples.story.plugins.environment.relation.BasicRelationPlugin import BasicRelationPlugin

RESOURCES_MAPS = {
    "BasicPerceivePlugin": BasicPerceivePlugin,
    "BasicPlanPlugin": BasicPlanPlugin,
    "BasicInvokePlugin": BasicInvokePlugin,
    "BasicStatePlugin": BasicStatePlugin,
    "BasicReflectPlugin": BasicReflectPlugin,
    "BasicMovePlugin": BasicMovePlugin,
    "BasicCommunicationPlugin": BasicCommunicationPlugin,
    "BasicOtherActionPlugin": BasicOtherActionPlugin,
    "BasicRelationPlugin": BasicRelationPlugin,
}
```

- [ ] **Step 6: 修复 BasicController.py 和 BasicPodManager.py 中的 import 路径**

在 `examples/story/BasicController.py` 和 `BasicPodManager.py` 中，将所有 `examples.story_of_the_stone` 替换为 `examples.story`：

```bash
sed -i '' 's/examples\.deduction/examples.story/g' examples/story/BasicController.py
sed -i '' 's/examples\.deduction/examples.story/g' examples/story/BasicPodManager.py
```

验证替换结果：
```bash
grep "examples\." examples/story/BasicController.py | head -5
grep "examples\." examples/story/BasicPodManager.py | head -5
```

- [ ] **Step 7: Commit**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
git add examples/story/
git commit -m "feat(story): scaffold story mode project structure from deduction"
```

---

## Task 2: 创建角色数据文件 `data/characters.json`

**Files:**
- Create: `examples/story/data/characters.json`

该文件为角色选择界面提供展示数据（28个可选角色 + 孙悟空 + 自定义）。

- [ ] **Step 1: 创建 `examples/story/data/characters.json`**

```json
[
  {
    "code": "5E9C2479",
    "id": "贾宝玉",
    "家族": "贾府（荣国府）",
    "性格": "温柔多情，叛逆不羁",
    "核心驱动": "追求真情与自由，厌恶仕途经济",
    "语言风格": "温文尔雅，情感细腻",
    "背景经历": "衔玉而生，贾母掌上明珠。与众姐妹共居大观园，诗情画意，却对科举仕途心存抵触。",
    "sprite": "../map/sprite/贾宝玉.png"
  },
  {
    "code": "97E26C8D",
    "id": "林黛玉",
    "家族": "林家（寄居贾府）",
    "性格": "敏感多愁，才华横溢",
    "核心驱动": "追求真挚爱情，用诗文寄托情感",
    "语言风格": "清丽婉转，字字珠玑，常含讽意",
    "背景经历": "父母早亡，寄居荣国府。与宝玉情深意切，才情出众，常以诗词抒发内心愁绪。",
    "sprite": "../map/sprite/林黛玉.png"
  },
  {
    "code": "39CA4675",
    "id": "薛宝钗",
    "家族": "薛家（金陵四大家族）",
    "性格": "稳重大方，处事周全",
    "核心驱动": "维护家族利益，以德服人",
    "语言风格": "温婉得体，言辞谨慎，少有锋芒",
    "背景经历": "薛家嫡女，进京待选才人。博学多识，深谙人情世故，在大观园中广受好评。",
    "sprite": "../map/sprite/薛宝钗.png"
  },
  {
    "code": "BD3440D6",
    "id": "史湘云",
    "家族": "史家（贾府候府）",
    "性格": "豪爽率真，乐观开朗",
    "核心驱动": "享受当下，以真性情待人",
    "语言风格": "爽朗白言，不拘小节，常带笑意",
    "背景经历": "父母早亡，由祖母抚养。性格豪爽，常扮男装嬉戏，与贾王姐妹情同兄弟，是大观园中最无无虑的存在。",
    "sprite": "../map/sprite/史湘云.png"
  },
  {
    "code": "489378AA",
    "id": "贾母",
    "家族": "贾府（荣国府）",
    "性格": "慈祥威严，精明睿智",
    "核心驱动": "守护家族荣耀与儿孙幸福",
    "语言风格": "慈和有度，一言九鼎",
    "背景经历": "荣国公遗孀，贾府最高权威。年迈但精神矍铄，深谙家族兴衰之道，对大观园有深厚感情。",
    "sprite": "../map/sprite/贾母.png"
  },
  {
    "code": "DE8FFE6E",
    "id": "王夫人",
    "家族": "贾府（荣国府）",
    "性格": "沉稳保守，信佛虔诚",
    "核心驱动": "维护家族秩序与儿子前途",
    "语言风格": "话少言重，不苟言笑",
    "背景经历": "贾政之妻，宝玉之母。掌管荣国府内宅，行事谨慎，信奉佛法，对下人严苛。",
    "sprite": "../map/sprite/王夫人.png"
  },
  {
    "code": "3C5C76D5",
    "id": "王熙凤",
    "家族": "贾府（荣国府）",
    "性格": "精明强干，泼辣机智",
    "核心驱动": "掌控权力，巩固地位",
    "语言风格": "伶牙俐齿，能言善辩，笑里藏刀",
    "背景经历": "贾琏之妻，王夫人之侄女。实际掌管荣国府大小事务，手段雷厉风行，却也心机深沉。",
    "sprite": "../map/sprite/王熙凤.png"
  },
  {
    "code": "A830F991",
    "id": "薛姨妈",
    "家族": "薛家（金陵四大家族）",
    "性格": "和善宽厚，八面玲珑",
    "核心驱动": "为子女谋划最好的前途",
    "语言风格": "温和周到，善于调和",
    "背景经历": "薛家当家，宝钗和薛蟠之母。进贾府后与王夫人来往密切，处处为女儿宝钗铺路。",
    "sprite": "../map/sprite/薛姨妈.png"
  },
  {
    "code": "34859931",
    "id": "贾政",
    "家族": "贾府（荣国府）",
    "性格": "迂腐正直，严肃古板",
    "核心驱动": "光耀门楣，培养贤才",
    "语言风格": "正言厉色，援引经典",
    "背景经历": "荣国府二老爷，宝玉之父。为官清正，奉行儒道，对宝玉寄予厚望却屡遭失望。",
    "sprite": "../map/sprite/贾政.png"
  },
  {
    "code": "748B6AED",
    "id": "贾元春",
    "家族": "贾府（荣国府）",
    "性格": "端庄贤淑，深明大义",
    "核心驱动": "光耀家族，护佑亲人",
    "语言风格": "皇家气派，措辞庄重",
    "背景经历": "宝玉之姐，入宫封妃。省亲时建造大观园，是家族荣耀的象征，身陷深宫却心系家人。",
    "sprite": "../map/sprite/贾元春.png"
  },
  {
    "code": "021C1E83",
    "id": "贾探春",
    "家族": "贾府（荣国府）",
    "性格": "英气果断，有勇有谋",
    "核心驱动": "改革家族积弊，实现自身价值",
    "语言风格": "直率果断，条理清晰",
    "背景经历": "贾政庶女，才干出众。曾主持荣国府改革，推行园田制，有"玫瑰花"之称，是大观园复兴的有力推手。",
    "sprite": "../map/sprite/贾探春.png"
  },
  {
    "code": "A7548FA8",
    "id": "贾迎春",
    "家族": "贾府（荣国府）",
    "性格": "温顺懦弱，与世无争",
    "核心驱动": "求得平静，避免冲突",
    "语言风格": "轻声细语，少有主见",
    "背景经历": "贾赦之女，性情懦弱，常被称为"二木头"。在大观园中低调度日，对复兴事业心有余而力不足。",
    "sprite": "../map/sprite/贾迎春.png"
  },
  {
    "code": "2E25BDFB",
    "id": "贾惜春",
    "家族": "贾府（宁国府）",
    "性格": "冷淡疏离，崇尚出世",
    "核心驱动": "远离尘世纷争，追求内心清净",
    "语言风格": "言简意赅，透着禅意",
    "背景经历": "宁国府贾珍之妹，自幼寄居荣国府。对家族事务漠然，醉心绘画，最终遁入空门。",
    "sprite": "../map/sprite/贾惜春.png"
  },
  {
    "code": "5E2D864D",
    "id": "李纨",
    "家族": "贾府（荣国府）",
    "性格": "贤淑守节，慈母之心",
    "核心驱动": "抚养贾兰，守节明志",
    "语言风格": "温和稳重，言辞守礼",
    "背景经历": "贾珠之遗孀，贾兰之母。守寡后专心抚育儿子，主持诗社，是大观园中最安稳的存在之一。",
    "sprite": "../map/sprite/李纨.png"
  },
  {
    "code": "3BAF4AFD",
    "id": "贾琏",
    "家族": "贾府（荣国府）",
    "性格": "圆滑世故，好色贪财",
    "核心驱动": "维持家族运转，谋取个人利益",
    "语言风格": "见风使舵，言辞滑溜",
    "背景经历": "贾赦之子，王熙凤之夫。负责对外交际与经济事务，虽有才干却品行不端。",
    "sprite": "../map/sprite/贾琏.png"
  },
  {
    "code": "0985ACF5",
    "id": "贾珍",
    "家族": "贾府（宁国府）",
    "性格": "放纵奢靡，骄横无礼",
    "核心驱动": "维持宁国府表面荣光，纵情享乐",
    "语言风格": "霸道自大，颐指气使",
    "背景经历": "宁国府族长，贾蓉之父。声色犬马，骄横无法，是家族颓败的代表人物之一。",
    "sprite": "../map/sprite/贾珍.png"
  },
  {
    "code": "D376CDC9",
    "id": "贾蓉",
    "家族": "贾府（宁国府）",
    "性格": "虚伪谄媚，唯利是图",
    "核心驱动": "巴结权贵，维护自身利益",
    "语言风格": "谄媚奉承，擅于逢迎",
    "背景经历": "贾珍之子，秦可卿之夫。依附父权，行事圆滑却缺乏主见，常跟随父亲参与各种宴乐。",
    "sprite": "../map/sprite/贾蓉.png"
  },
  {
    "code": "46B0FF71",
    "id": "贾环",
    "家族": "贾府（荣国府）",
    "性格": "阴险刻薄，自卑嫉妒",
    "核心驱动": "争得更多关注与地位",
    "语言风格": "阴阳怪气，满含戾气",
    "背景经历": "贾政庶子，赵姨娘之子。因庶出身份备受歧视，内心阴暗，常暗中破坏他人。",
    "sprite": "../map/sprite/贾环.png"
  },
  {
    "code": "6DD386E4",
    "id": "赵姨娘",
    "家族": "贾府（荣国府）",
    "性格": "嫉妒偏激，自私狭隘",
    "核心驱动": "为儿子贾环争得地位",
    "语言风格": "粗鄙直白，满腹牢骚",
    "背景经历": "贾政之妾，贾环与贾探春之母。地位低下，常生事端，是荣国府的不安定因素。",
    "sprite": "../map/sprite/赵姨娘.png"
  },
  {
    "code": "2C67C0AD",
    "id": "薛蟠",
    "家族": "薛家（金陵四大家族）",
    "性格": "粗鲁莽撞，横行霸道",
    "核心驱动": "随心所欲，肆意妄为",
    "语言风格": "粗口连连，蛮横无理",
    "背景经历": "薛家长子，宝钗之兄。仗势欺人，曾打死人命。随母进京后在贾府附近居住，是麻烦制造者。",
    "sprite": "../map/sprite/薛蟠.png"
  },
  {
    "code": "62180E4B",
    "id": "袭人",
    "家族": "贾府（荣国府丫鬟）",
    "性格": "温柔体贴，忠心耿耿",
    "核心驱动": "服侍好宝玉，维护大观园秩序",
    "语言风格": "温柔细腻，言辞得体",
    "背景经历": "宝玉贴身丫鬟，原名珍珠。对宝玉忠心护主，行事稳重，深受王夫人信任。",
    "sprite": "../map/sprite/袭人.png"
  },
  {
    "code": "5B987587",
    "id": "晴雯",
    "家族": "贾府（荣国府丫鬟）",
    "性格": "刚烈直爽，爱憎分明",
    "核心驱动": "忠于自我，不向权贵低头",
    "语言风格": "伶牙俐齿，快人快语",
    "背景经历": "宝玉大丫鬟，容貌出众，针线绝佳。性格刚烈，不肯委屈求全，被王夫人以"狐媚子"之名驱逐。",
    "sprite": "../map/sprite/晴雯.png"
  },
  {
    "code": "AC6AE5AA",
    "id": "紫鹃",
    "家族": "贾府（荣国府丫鬟）",
    "性格": "聪慧忠诚，心思细腻",
    "核心驱动": "守护黛玉，为主谋划",
    "语言风格": "温柔中透着机敏",
    "背景经历": "林黛玉的贴身丫鬟，对黛玉情同姐妹，忠心护主，对宝黛爱情心知肚明。",
    "sprite": "../map/sprite/紫鹃.png"
  },
  {
    "code": "CA5042E8",
    "id": "麝月",
    "家族": "贾府（荣国府丫鬟）",
    "性格": "平和稳重，尽职尽责",
    "核心驱动": "安分守己，照顾好身边人",
    "语言风格": "平实温和，少有张扬",
    "背景经历": "宝玉丫鬟之一，性情平和，在众丫鬟中以稳重著称，始终坚守本分。",
    "sprite": "../map/sprite/麝月.png"
  },
  {
    "code": "7C0C434B",
    "id": "平儿",
    "家族": "贾府（荣国府丫鬟）",
    "性格": "聪明伶俐，善解人意",
    "核心驱动": "在凤姐与众人间维持平衡",
    "语言风格": "体贴周到，善于斡旋",
    "背景经历": "王熙凤的陪嫁丫鬟兼通房，为人善良，夹在主子与下人之间，常化解矛盾。",
    "sprite": "../map/sprite/平儿.png"
  },
  {
    "code": "CD8CFDBB",
    "id": "鸳鸯",
    "家族": "贾府（荣国府丫鬟）",
    "性格": "刚烈忠贞，不畏权贵",
    "核心驱动": "守护贾母，守护自身尊严",
    "语言风格": "正直有力，掷地有声",
    "背景经历": "贾母的贴身丫鬟，聪明忠心，曾拒绝贾赦的无理纳妾要求。贾母最信任之人。",
    "sprite": "../map/sprite/鸳鸯.png"
  },
  {
    "code": "743001FD",
    "id": "妙玉",
    "家族": "无（出家人，寄居栊翠庵）",
    "性格": "清高孤傲，洁癖严重",
    "核心驱动": "追求精神纯净，远离世俗污浊",
    "语言风格": "超凡脱俗，禅意隐约",
    "背景经历": "官宦之女，因体弱出家，随师进京后住在大观园栊翠庵。洁癖严重，对大多数人冷淡疏离。",
    "sprite": "../map/sprite/妙玉.png"
  },
  {
    "code": "SWK00001",
    "id": "孙悟空",
    "家族": "花果山水帘洞",
    "性格": "嫉恶如仇，神通广大",
    "核心驱动": "降妖除魔，保护弱小",
    "语言风格": "豪迈直接，充满江湖气",
    "背景经历": "大闹天宫的齐天大圣，保唐僧西天取经后修成正果。因缘际会来到大观园，以神通之力助力复兴。",
    "sprite": "../map/sprite/孙悟空.png"
  }
]
```

- [ ] **Step 2: Commit**

```bash
git add examples/story/data/characters.json
git commit -m "feat(story): add character selection data for 27 red chamber characters + sun wukong"
```

---

## Task 3: 角色选择界面

**Files:**
- Create: `examples/story/frontend/character_select.html`
- Create: `examples/story/frontend/character_select.js`
- Create: `examples/story/frontend/character_select.css`

**交互流程：**
1. 页面加载时从 `../data/characters.json` 读取28个角色 + 自定义选项
2. 点击角色卡片 → 高亮选中，右侧显示详细信息
3. 点击"开始复兴"按钮 → 将选中角色存入 `localStorage('story_player_character')` → 跳转 `index.html`

- [ ] **Step 1: 创建 `character_select.css`**

文件内容（`examples/story/frontend/character_select.css`）：
```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;600;700&family=Ma+Shan+Zheng&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: #1a0f07;
  color: #d4c4a8;
  font-family: 'Noto Serif SC', serif;
  min-height: 100vh;
  overflow: hidden;
}

.bg-texture {
  position: fixed; inset: 0;
  background: 
    radial-gradient(ellipse at 30% 20%, rgba(139,90,43,0.15) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 80%, rgba(80,40,10,0.2) 0%, transparent 50%);
  pointer-events: none;
}

.select-header {
  text-align: center;
  padding: 24px 20px 12px;
  border-bottom: 1px solid rgba(180,140,60,0.3);
}

.select-header h1 {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 2.2rem;
  color: #c8a96e;
  letter-spacing: 0.15em;
  text-shadow: 0 0 20px rgba(200,169,110,0.4);
}

.select-header p {
  color: #8a7560;
  font-size: 0.85rem;
  margin-top: 4px;
  letter-spacing: 0.1em;
}

.select-layout {
  display: flex;
  height: calc(100vh - 90px);
}

/* 左侧角色网格 */
.char-grid-panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  border-right: 1px solid rgba(180,140,60,0.2);
}

.char-grid-panel::-webkit-scrollbar { width: 4px; }
.char-grid-panel::-webkit-scrollbar-thumb { background: rgba(180,140,60,0.4); border-radius: 2px; }

.char-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 12px;
}

.char-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 6px;
  border-radius: 8px;
  border: 1px solid rgba(180,140,60,0.2);
  background: rgba(255,255,255,0.03);
  cursor: pointer;
  transition: all 0.2s;
}

.char-card:hover {
  border-color: rgba(200,169,110,0.5);
  background: rgba(200,169,110,0.08);
  transform: translateY(-2px);
}

.char-card.selected {
  border-color: #c8a96e;
  background: rgba(200,169,110,0.15);
  box-shadow: 0 0 12px rgba(200,169,110,0.3);
}

.char-card img {
  width: 56px;
  height: 56px;
  object-fit: contain;
  image-rendering: pixelated;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
}

.char-card .char-name {
  font-size: 0.75rem;
  color: #c8a96e;
  text-align: center;
  line-height: 1.2;
}

/* 自定义角色卡 */
.char-card.custom-card img {
  opacity: 0.6;
  filter: none;
}

/* 右侧详情面板 */
.char-detail-panel {
  width: 320px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.detail-portrait {
  text-align: center;
}

.detail-portrait img {
  width: 96px;
  height: 96px;
  object-fit: contain;
  image-rendering: pixelated;
  filter: drop-shadow(0 4px 12px rgba(200,169,110,0.4));
}

.detail-portrait .detail-name {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.6rem;
  color: #c8a96e;
  margin-top: 8px;
}

.detail-info {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(180,140,60,0.2);
  border-radius: 8px;
  padding: 14px;
  font-size: 0.82rem;
  line-height: 1.8;
}

.detail-info .info-row {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid rgba(180,140,60,0.1);
  padding-bottom: 6px;
  margin-bottom: 6px;
}

.detail-info .info-row:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.info-label {
  color: #8a7560;
  min-width: 56px;
  flex-shrink: 0;
}

.info-value {
  color: #d4c4a8;
}

.detail-bg {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(180,140,60,0.2);
  border-radius: 8px;
  padding: 14px;
  font-size: 0.82rem;
  line-height: 1.7;
  color: #a89880;
  flex: 1;
}

.start-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, rgba(180,120,30,0.8), rgba(140,80,20,0.8));
  border: 1px solid rgba(200,169,110,0.5);
  border-radius: 8px;
  color: #f0e0c0;
  font-family: 'Noto Serif SC', serif;
  font-size: 1rem;
  letter-spacing: 0.15em;
  cursor: pointer;
  transition: all 0.2s;
}

.start-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(200,140,40,0.9), rgba(160,100,30,0.9));
  box-shadow: 0 0 20px rgba(200,169,110,0.4);
}

.start-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.empty-hint {
  text-align: center;
  color: #6a5a40;
  font-size: 0.85rem;
  margin-top: 40px;
}
```

- [ ] **Step 2: 创建 `character_select.html`**

文件内容（`examples/story/frontend/character_select.html`）：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>复兴大观园 · 选择人物</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="character_select.css" />
</head>
<body>
  <div class="bg-texture"></div>

  <header class="select-header">
    <h1>复兴大观园</h1>
    <p>请选择你要扮演的人物，带领大观园走向复兴</p>
  </header>

  <div class="select-layout">
    <!-- 左侧：角色网格 -->
    <div class="char-grid-panel">
      <div class="char-grid" id="charGrid">
        <!-- 由 JS 动态生成 -->
      </div>
    </div>

    <!-- 右侧：角色详情 + 开始按钮 -->
    <div class="char-detail-panel">
      <div id="charDetail">
        <p class="empty-hint">← 请从左侧选择你要扮演的人物</p>
      </div>
      <button class="start-btn" id="startBtn" disabled onclick="startGame()">
        开始复兴大业
      </button>
    </div>
  </div>

  <script src="character_select.js"></script>
</body>
</html>
```

- [ ] **Step 3: 创建 `character_select.js`**

文件内容（`examples/story/frontend/character_select.js`）：
```javascript
let characters = [];
let selectedCharacter = null;

async function loadCharacters() {
  try {
    const resp = await fetch('../data/characters.json');
    characters = await resp.json();
    renderGrid();
  } catch (e) {
    console.error('Failed to load characters:', e);
  }
}

function renderGrid() {
  const grid = document.getElementById('charGrid');
  grid.innerHTML = '';

  characters.forEach(char => {
    const card = document.createElement('div');
    card.className = 'char-card';
    card.dataset.id = char.id;
    card.innerHTML = `
      <img src="${char.sprite}" alt="${char.id}" onerror="this.src='../map/sprite/普通人.png'" />
      <span class="char-name">${char.id}</span>
    `;
    card.addEventListener('click', () => selectCharacter(char));
    grid.appendChild(card);
  });

  // 自定义角色
  const customCard = document.createElement('div');
  customCard.className = 'char-card custom-card';
  customCard.innerHTML = `
    <img src="../map/sprite/普通人.png" alt="自定义" />
    <span class="char-name">自定义</span>
  `;
  customCard.addEventListener('click', openCustomModal);
  grid.appendChild(customCard);
}

function selectCharacter(char) {
  selectedCharacter = char;
  document.querySelectorAll('.char-card').forEach(c => c.classList.remove('selected'));
  const card = document.querySelector(`.char-card[data-id="${char.id}"]`);
  if (card) card.classList.add('selected');
  renderDetail(char);
  document.getElementById('startBtn').disabled = false;
}

function renderDetail(char) {
  document.getElementById('charDetail').innerHTML = `
    <div class="detail-portrait">
      <img src="${char.sprite}" alt="${char.id}" onerror="this.src='../map/sprite/普通人.png'" />
      <div class="detail-name">${char.id}</div>
    </div>
    <div class="detail-info">
      <div class="info-row">
        <span class="info-label">家族</span>
        <span class="info-value">${char['家族'] || '—'}</span>
      </div>
      <div class="info-row">
        <span class="info-label">性格</span>
        <span class="info-value">${char['性格'] || '—'}</span>
      </div>
      <div class="info-row">
        <span class="info-label">核心驱动</span>
        <span class="info-value">${char['核心驱动'] || '—'}</span>
      </div>
      <div class="info-row">
        <span class="info-label">语言风格</span>
        <span class="info-value">${char['语言风格'] || '—'}</span>
      </div>
    </div>
    <div class="detail-bg">${char['背景经历'] || '—'}</div>
  `;
}

function openCustomModal() {
  // 简单 prompt 交互（可后续升级为弹窗）
  const name = prompt('请输入自定义人物名称：');
  if (!name || !name.trim()) return;
  const customChar = {
    code: 'CUSTOM_' + Date.now(),
    id: name.trim(),
    '家族': '自定义',
    '性格': prompt('性格（可留空）：') || '待定',
    '核心驱动': prompt('核心驱动（可留空）：') || '参与大观园复兴',
    '语言风格': '自然',
    '背景经历': prompt('背景经历（可留空）：') || '来历神秘的人物。',
    sprite: '../map/sprite/普通人.png',
    isCustom: true
  };
  characters.push(customChar);
  renderGrid();
  selectCharacter(customChar);
}

function startGame() {
  if (!selectedCharacter) return;
  localStorage.setItem('story_player_character', JSON.stringify(selectedCharacter));
  window.location.href = 'index.html';
}

loadCharacters();
```

- [ ] **Step 4: 验证页面可访问（需先启动 story 服务）**

启动后访问 `http://localhost:8001/frontend/character_select.html`，确认：
- 27+1个角色卡片正确显示精灵图和名字
- 点击角色后右侧显示详细信息
- "开始复兴大业"按钮在未选中时灰色，选中后可点击

- [ ] **Step 5: Commit**

```bash
git add examples/story/frontend/character_select.html examples/story/frontend/character_select.js examples/story/frontend/character_select.css
git commit -m "feat(story): add character selection screen with profile display"
```

---

## Task 4: 剧情模式主 UI（index.html + style.css）

**Files:**
- Create: `examples/story/frontend/index.html`
- Create: `examples/story/frontend/style.css`

**UI 布局（与截图对齐）：**
```
┌──────────────────── Header（与自由模式一致）────────────────────┐
│  万象谱 · 复兴大观园    [日期]    [设置][开始推演][模拟]  Tick ◀▶ │
├──────────────┬──────────────────────────┬──────────────────────┤
│ 玩家角色区    │                          │   目标面板           │
│  [头像]      │    地图（同deduction）    │   稳定度: 58/100     │
│  角色名      │                          │   [====------]       │
│  [下达任务]  │                          │   历史事件记录        │
│  [跳过任务]  │                          │   - 贾探春修缮...+10  │
│──────────────│                          │   - 薛蟠大闹...-10   │
│ 其他角色列表 │                          │                      │
│  [卡片...]   │                          │                      │
└──────────────┴──────────────────────────┴──────────────────────┘
```

- [ ] **Step 1: 创建 `style.css`（基于 deduction/style.css 扩展）**

```bash
# 先复制基础样式
cp examples/story_of_the_stone/frontend/style.css examples/story/frontend/style.css
```

然后在文件末尾追加以下剧情模式专用样式：
```css
/* ===== 剧情模式专用样式 ===== */

/* 覆盖标题 */
.header-sub { font-size: 0.8rem; opacity: 0.7; }

/* 左侧边栏：玩家角色区 + 其他角色列表 */
.player-zone {
  padding: 12px;
  border-bottom: 1px solid rgba(180,140,60,0.3);
  margin-bottom: 8px;
}

.player-portrait {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.player-portrait img {
  width: 48px;
  height: 48px;
  object-fit: contain;
  image-rendering: pixelated;
  border-radius: 4px;
  border: 1px solid rgba(200,169,110,0.4);
  background: rgba(0,0,0,0.3);
}

.player-name {
  font-size: 1rem;
  color: #c8a96e;
  font-weight: 600;
}

.player-role-tag {
  font-size: 0.65rem;
  color: #8a7560;
  background: rgba(180,140,60,0.15);
  padding: 1px 6px;
  border-radius: 3px;
  margin-top: 2px;
}

.player-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.btn-assign-task {
  width: 100%;
  padding: 8px;
  background: linear-gradient(135deg, rgba(140,90,20,0.8), rgba(100,60,10,0.8));
  border: 1px solid rgba(200,169,110,0.4);
  border-radius: 6px;
  color: #f0e0c0;
  font-family: 'Noto Serif SC', serif;
  font-size: 0.82rem;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-assign-task:hover {
  background: linear-gradient(135deg, rgba(180,120,30,0.9), rgba(140,80,20,0.9));
  border-color: rgba(200,169,110,0.7);
}

.btn-skip-task {
  width: 100%;
  padding: 6px;
  background: transparent;
  border: 1px solid rgba(180,140,60,0.25);
  border-radius: 6px;
  color: #8a7560;
  font-family: 'Noto Serif SC', serif;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-skip-task:hover {
  border-color: rgba(180,140,60,0.5);
  color: #a89870;
}

/* 右侧目标面板 */
.goal-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 240px;
  background: rgba(20,12,5,0.88);
  border: 1px solid rgba(180,140,60,0.35);
  border-radius: 10px;
  padding: 14px;
  backdrop-filter: blur(8px);
  z-index: 10;
}

.goal-panel-title {
  font-size: 0.7rem;
  color: #8a7560;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.goal-score-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 8px;
}

.goal-score-num {
  font-size: 2rem;
  font-weight: 700;
  color: #c8a96e;
  line-height: 1;
}

.goal-score-max {
  font-size: 0.85rem;
  color: #6a5a40;
}

.goal-progress-track {
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  margin-bottom: 12px;
  overflow: hidden;
}

.goal-progress-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #8b5e1a, #c8a96e);
  transition: width 0.6s ease;
}

.goal-progress-fill.danger {
  background: linear-gradient(90deg, #8b1a1a, #c86e6e);
}

.goal-progress-fill.success {
  background: linear-gradient(90deg, #1a6e2e, #6ec87e);
}

.goal-events-title {
  font-size: 0.7rem;
  color: #6a5a40;
  margin-bottom: 6px;
  letter-spacing: 0.1em;
}

.goal-events-list {
  max-height: 180px;
  overflow-y: auto;
  font-size: 0.72rem;
  line-height: 1.5;
}

.goal-events-list::-webkit-scrollbar { width: 3px; }
.goal-events-list::-webkit-scrollbar-thumb { background: rgba(180,140,60,0.3); }

.goal-event-item {
  padding: 4px 0;
  border-bottom: 1px solid rgba(180,140,60,0.1);
  display: flex;
  gap: 6px;
  align-items: flex-start;
}

.goal-event-item:last-child { border-bottom: none; }

.event-delta {
  font-weight: 700;
  min-width: 28px;
  flex-shrink: 0;
}

.event-delta.plus { color: #6ec87e; }
.event-delta.minus { color: #c86e6e; }

.event-text { color: #8a7560; }

/* 胜负结局覆盖层 */
.game-result-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  display: none;
}

.game-result-overlay.show { display: flex; }

.game-result-title {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 3.5rem;
  color: #c8a96e;
  text-shadow: 0 0 40px rgba(200,169,110,0.6);
  margin-bottom: 20px;
}

.game-result-title.fail { color: #c86e6e; text-shadow: 0 0 40px rgba(200,110,110,0.6); }

.game-result-desc {
  color: #8a7560;
  font-size: 1rem;
  margin-bottom: 30px;
  text-align: center;
  max-width: 400px;
  line-height: 1.8;
}

.game-result-btn {
  padding: 12px 40px;
  background: rgba(140,90,20,0.8);
  border: 1px solid rgba(200,169,110,0.5);
  border-radius: 8px;
  color: #f0e0c0;
  font-family: 'Noto Serif SC', serif;
  font-size: 0.95rem;
  cursor: pointer;
}

/* 下达任务弹窗 */
#assignTaskModal .modal-content { max-width: 460px; }
```

- [ ] **Step 2: 创建 `index.html`**

完整文件内容（`examples/story/frontend/index.html`）：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>万象谱 · 复兴大观园</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;600;700&family=Ma+Shan+Zheng&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div class="ink-bg"></div>
  <div class="grain"></div>

  <!-- 胜负结局覆盖层 -->
  <div id="gameResultOverlay" class="game-result-overlay">
    <div class="game-result-title" id="gameResultTitle">复兴成功</div>
    <div class="game-result-desc" id="gameResultDesc">大观园在众人努力下重焕生机，往日繁荣再现。</div>
    <button class="game-result-btn" onclick="restartGame()">重新开始</button>
  </div>

  <!-- Header -->
  <header class="header">
    <div class="header-left">
      <h1 class="header-title">万象谱</h1>
      <span class="header-sub">复兴大观园 · 剧情模式</span>
    </div>
    <div class="header-center">
      <span class="sim-date" id="simDate">乾隆四十九年 正月初一 子时</span>
    </div>
    <div class="header-right">
      <button id="settingsBtn" class="control-btn settings-btn" onclick="openSettingsModal()" title="设置">
        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
      <button id="startTickBtn" class="control-btn" onclick="sendStartTick()">开始推演</button>
      <button id="applyTickBtn" class="control-btn control-btn-apply" onclick="applyPendingTick()" disabled>开始模拟</button>
      <div class="status-dot" id="statusDot"></div>
      <span class="status-text" id="statusText">连接中…</span>
      <div class="tick-nav" style="display:inline-flex;align-items:center;margin-left:15px;">
        <button id="prevTickBtn" class="tick-nav-btn" onclick="prevTick()" disabled style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:#d4c4a8;cursor:pointer;padding:2px 8px;border-radius:4px 0 0 4px;">&lt;</button>
        <span class="tick-badge" style="margin-left:0;border-radius:0;">Tick <span id="tickNum">—</span></span>
        <button id="nextTickBtn" class="tick-nav-btn" onclick="nextTick()" disabled style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:#d4c4a8;cursor:pointer;padding:2px 8px;border-radius:0 4px 4px 0;">&gt;</button>
      </div>
    </div>
  </header>

  <div class="layout">
    <!-- 左侧边栏：玩家角色区 + 其他角色列表 -->
    <aside class="sidebar">
      <!-- 玩家角色区 -->
      <div class="player-zone" id="playerZone">
        <div class="player-portrait">
          <img id="playerSprite" src="../map/sprite/普通人.png" alt="玩家角色" />
          <div>
            <div class="player-name" id="playerName">—</div>
            <div class="player-role-tag">扮演中</div>
          </div>
        </div>
        <div class="player-actions">
          <button class="btn-assign-task" onclick="openAssignTaskModal()">下达任务</button>
          <button class="btn-skip-task" onclick="skipTask()">跳过下达任务</button>
        </div>
      </div>

      <!-- 其他角色列表 -->
      <div class="sidebar-title">其他人物</div>
      <div class="agent-list" id="agentList">
        <div class="agent-placeholder">等待数据…</div>
      </div>
    </aside>

    <!-- 主内容：地图 -->
    <main class="main-content" id="mainContent">
      <div id="mapContainer" class="map-container">
        <canvas id="mapCanvas"></canvas>
        <div class="map-loading" id="mapLoading">正在加载地图…</div>
      </div>

      <!-- 目标面板（右上角浮层） -->
      <div class="goal-panel" id="goalPanel">
        <div class="goal-panel-title">复兴大观园 · 稳定度</div>
        <div class="goal-score-row">
          <span class="goal-score-num" id="goalScoreNum">50</span>
          <span class="goal-score-max">/ 100</span>
        </div>
        <div class="goal-progress-track">
          <div class="goal-progress-fill" id="goalProgressFill" style="width:50%"></div>
        </div>
        <div class="goal-events-title">历史事件</div>
        <div class="goal-events-list" id="goalEventsList">
          <div class="goal-event-item">
            <span class="event-delta" style="color:#8a7560">—</span>
            <span class="event-text">等待推演开始…</span>
          </div>
        </div>
      </div>

      <!-- 人物详情悬浮框 -->
      <div id="agentDetailBox" class="agent-detail-box">
        <div class="detail-box-header">
          <span class="detail-box-title">人物档案</span>
          <button class="detail-box-close" onclick="closeAgentDetail()">&times;</button>
        </div>
        <div id="detailPanel" class="detail-panel-content">
          <div class="empty-state">
            <div class="empty-icon">卷</div>
            <p>请从左侧选择人物</p>
          </div>
        </div>
      </div>
    </main>
  </div>

  <!-- 对话侧边栏（同deduction） -->
  <div id="dialogueModal" class="dialogue-sidebar">
    <div class="sidebar-header">
      <span class="modal-title">对话详录</span>
      <span class="close-btn" onclick="closeModal()">&times;</span>
    </div>
    <div id="dialogueSummary" class="modal-summary" style="display:none"></div>
    <div class="sidebar-content">
      <section id="dialogueParticipantsCard" class="dialogue-participants-card">
        <div class="dialogue-side-title">对话人物</div>
        <div id="dialogueParticipants" class="dialogue-participants"></div>
      </section>
      <div id="dialogueContent" class="dialogue-body"></div>
      <section class="dream-thumbnail-card">
        <div class="dialogue-side-title">红楼梦略缩图</div>
        <div class="dream-thumbnail-frame dream-thumbnail-frame-portrait">
          <canvas id="dialogueMiniMapCanvas" class="dream-thumbnail-canvas"></canvas>
          <div class="dream-map-vignette"></div>
          <div class="dream-location-overlay">
            <span class="dream-location-label">对话地点</span>
            <strong id="dialogueLocationName" class="dream-location-name">待定位</strong>
          </div>
        </div>
      </section>
    </div>
  </div>

  <!-- 下达任务弹窗 -->
  <div id="assignTaskModal" class="modal">
    <div class="modal-content" style="max-width:460px;">
      <div class="modal-header">
        <span class="modal-title">为 <span id="assignTaskCharName">—</span> 下达任务</span>
        <span class="close-btn" onclick="closeAssignTaskModal()">&times;</span>
      </div>
      <div class="modal-body" style="padding:20px;">
        <div class="add-agent-form">
          <div class="form-group">
            <label>行动内容 <span class="required">*</span></label>
            <textarea id="assignTaskAction" rows="3" placeholder="例如：前往怡红院，召集众人商议修缮计划"></textarea>
          </div>
          <div class="form-group">
            <label>目标人物（可选）</label>
            <input type="text" id="assignTaskTarget" placeholder="例如：贾探春" />
          </div>
          <div class="form-group">
            <label>目标地点（可选）</label>
            <input type="text" id="assignTaskLocation" placeholder="例如：怡红院" />
          </div>
          <div class="form-actions">
            <button class="btn-secondary" onclick="closeAssignTaskModal()">取消</button>
            <button class="btn-primary" onclick="submitAssignTask()">确认下达</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 设置弹窗（同deduction） -->
  <div id="settingsModal" class="modal">
    <div class="modal-content" style="max-width:500px;">
      <div class="modal-header">
        <span class="modal-title">系统设置</span>
        <span class="close-btn" onclick="closeSettingsModal()">&times;</span>
      </div>
      <div class="modal-body" style="padding:20px;">
        <div class="add-agent-form">
          <div class="form-divider"><span>系统操作</span></div>
          <div class="form-group">
            <button id="resetBtn" class="control-btn" onclick="confirmReset()" style="background:rgba(192,57,43,0.8);border-color:#c0392b;width:100%;padding:10px;">重置系统</button>
          </div>
          <div class="form-divider"><span>模型配置</span></div>
          <div class="form-group">
            <label>API Base URL</label>
            <input type="text" id="settingsBaseUrl" placeholder="https://api.openai.com/v1" />
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input type="password" id="settingsApiKey" placeholder="sk-..." />
          </div>
          <div class="form-group">
            <label>Model</label>
            <input type="text" id="settingsModel" placeholder="gpt-4o" />
          </div>
          <div class="form-actions">
            <button class="btn-secondary" onclick="closeSettingsModal()">取消</button>
            <button class="btn-primary" onclick="saveSettings()">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script src="i18n.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add examples/story/frontend/index.html examples/story/frontend/style.css
git commit -m "feat(story): add story mode main UI with player zone and goal panel"
```

---

## Task 5: 主游戏逻辑 app.js

**Files:**
- Create: `examples/story/frontend/app.js`

基于 `examples/story_of_the_stone/frontend/app.js` 改造，主要增加：
1. 从 localStorage 读取玩家角色，渲染左侧玩家区
2. 接收 WebSocket 广播中的 `story_score` 和 `score_events`，更新目标面板
3. "下达任务" / "跳过任务" 按钮逻辑
4. 胜负判断与结局界面

- [ ] **Step 1: 复制 deduction/app.js 并修改**

```bash
cp examples/story_of_the_stone/frontend/app.js examples/story/frontend/app.js
```

- [ ] **Step 2: 在 `app.js` 开头添加剧情模式初始化代码**

在文件顶部（第一行）前插入：
```javascript
// ===== 剧情模式：玩家角色初始化 =====
let playerCharacter = null;
let pendingTaskTick = null; // 玩家等待下达任务的 tick

function initPlayerCharacter() {
  const stored = localStorage.getItem('story_player_character');
  if (!stored) {
    window.location.href = 'character_select.html';
    return;
  }
  playerCharacter = JSON.parse(stored);
  document.getElementById('playerName').textContent = playerCharacter.id;
  const sprite = document.getElementById('playerSprite');
  sprite.src = playerCharacter.sprite || '../map/sprite/普通人.png';
  sprite.onerror = () => { sprite.src = '../map/sprite/普通人.png'; };
  document.getElementById('assignTaskCharName').textContent = playerCharacter.id;
}

// ===== 下达任务 =====
function openAssignTaskModal() {
  document.getElementById('assignTaskAction').value = '';
  document.getElementById('assignTaskTarget').value = '';
  document.getElementById('assignTaskLocation').value = '';
  document.getElementById('assignTaskModal').style.display = 'flex';
}

function closeAssignTaskModal() {
  document.getElementById('assignTaskModal').style.display = 'none';
}

async function submitAssignTask() {
  const action = document.getElementById('assignTaskAction').value.trim();
  if (!action) { alert('请输入行动内容'); return; }
  const target = document.getElementById('assignTaskTarget').value.trim();
  const location = document.getElementById('assignTaskLocation').value.trim();

  // 复用 server.py 已有的 WebSocket set_plan 处理器（无需新 REST 端点）
  // server.py 中 set_plan 会将 user_plan:{agent_id} 写入 Redis
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'set_plan',
      agent_id: playerCharacter.id,
      action: action,
      target: target || null,
      location: location || ''
    }));
    closeAssignTaskModal();
    showToast(`已为 ${playerCharacter.id} 下达任务`);
  } else {
    alert('WebSocket 未连接，请检查服务器状态');
  }
}

function skipTask() {
  showToast('已跳过本轮任务下达，将由 AI 自动规划');
}

// ===== 目标面板：分数更新 =====
function updateGoalPanel(score, events) {
  if (score === undefined || score === null) return;
  
  const scoreNum = document.getElementById('goalScoreNum');
  const fill = document.getElementById('goalProgressFill');
  
  scoreNum.textContent = score;
  const pct = Math.max(0, Math.min(100, score));
  fill.style.width = pct + '%';
  
  fill.classList.remove('danger', 'success');
  if (score <= 20) fill.classList.add('danger');
  else if (score >= 80) fill.classList.add('success');

  // 更新历史事件
  if (events && events.length > 0) {
    const list = document.getElementById('goalEventsList');
    events.forEach(ev => {
      const item = document.createElement('div');
      item.className = 'goal-event-item';
      const delta = ev.delta > 0 ? `+${ev.delta}` : `${ev.delta}`;
      const cls = ev.delta > 0 ? 'plus' : 'minus';
      item.innerHTML = `
        <span class="event-delta ${cls}">${delta}</span>
        <span class="event-text">${ev.reason}</span>
      `;
      list.insertBefore(item, list.firstChild);
    });
    // 最多保留30条
    while (list.children.length > 30) list.removeChild(list.lastChild);
  }

  // 胜负判断
  if (score >= 100) showGameResult(true);
  else if (score <= 0) showGameResult(false);
}

// ===== 胜负结局 =====
function showGameResult(isWin) {
  const overlay = document.getElementById('gameResultOverlay');
  const title = document.getElementById('gameResultTitle');
  const desc = document.getElementById('gameResultDesc');
  
  if (isWin) {
    title.textContent = '复兴成功';
    title.className = 'game-result-title';
    desc.textContent = '大观园在众人努力下重焕生机，往日的诗意繁华再度降临。';
  } else {
    title.textContent = '大观园衰败';
    title.className = 'game-result-title fail';
    desc.textContent = '稳定度跌至谷底，大观园终究未能逃脱颓败的命运。';
  }
  overlay.classList.add('show');
}

function restartGame() {
  localStorage.removeItem('story_player_character');
  window.location.href = 'character_select.html';
}

function showToast(msg) {
  // 简单 toast 提示
  const t = document.createElement('div');
  t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:rgba(30,20,10,0.9);border:1px solid rgba(200,169,110,0.4);color:#c8a96e;padding:8px 20px;border-radius:6px;font-size:0.82rem;z-index:9999;pointer-events:none;';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}
```

- [ ] **Step 3: 修改 WebSocket 数据接收，监听 `story_score_update` 消息**

在 app.js 中找到处理 WebSocket 消息的 `ws.onmessage` 回调，在 `switch(msg.type)` 或 `if/else` 链中新增：

```javascript
// 在 ws.onmessage 的消息分发中添加（与 "tick_update" 并列）：
} else if (msg.type === 'story_score_update') {
  updateGoalPanel(msg.story_score, msg.score_events || []);
}
```

> **背景：** `broadcast_tick_data` 发出 `type: "tick_update"` 消息；分数通过独立的 `type: "story_score_update"` 消息发出，两者分开处理。

- [ ] **Step 4: 修改 app.js 末尾的初始化调用**

在 app.js 末尾找到 `DOMContentLoaded` 或初始化逻辑，添加：
```javascript
initPlayerCharacter();
```

- [ ] **Step 5: 修改 agentList 渲染，排除玩家角色**

在 app.js 中找到 `renderAgentList` 或类似函数，添加过滤：
```javascript
// 过滤掉玩家自己的角色，不在"其他角色"列表中显示
const otherAgents = agentsData.filter(a => 
  !playerCharacter || a.id !== playerCharacter.id
);
// 用 otherAgents 替换原来的 agentsData 渲染
```

- [ ] **Step 6: Commit**

```bash
git add examples/story/frontend/app.js
git commit -m "feat(story): add story mode app.js with player control and goal panel logic"
```

---

## Task 6: 修改 ReflectPlugin — 分数评估逻辑（核心）

**Files:**
- Create: `examples/story/plugins/agent/reflect/BasicReflectPlugin.py`

在 deduction 版本基础上增加两个新方法：
- `_evaluate_score_contribution()` — 每 tick 评估当前行动对稳定度的影响
- 在 `_check_life_status_lightweight()` 中角色离场时自动 -10

- [ ] **Step 1: 复制并创建基础文件**

```bash
cp examples/story_of_the_stone/plugins/agent/reflect/BasicReflectPlugin.py \
   examples/story/plugins/agent/reflect/BasicReflectPlugin.py
```

- [ ] **Step 2: 在 `BasicReflectPlugin` 的 `__init__` 中添加 Redis 客户端**

在 `__init__` 方法中增加 redis 参数：
```python
# 文件顶部增加 import
import json

class BasicReflectPlugin(ReflectPlugin):
    def __init__(self, redis=None) -> None:
        super().__init__()
        self.model = None
        self.agent_id = None
        self.redis = redis  # 用于更新全局分数

    async def init(self) -> None:
        self.agent_id = self._component.agent.agent_id
        self.model = self._component.agent.model
        # 如果未通过参数注入，尝试从 state 组件的 redis 获取
        if self.redis is None:
            try:
                state_component = self._component.agent.get_component("state")
                state_plugin = state_component.get_plugin()
                self.redis = state_plugin.redis
            except Exception:
                pass
        logger.info(f"[{self.agent_id}][N/A] BasicReflectPlugin (story) initialized")
```

- [ ] **Step 3: 修改 `execute()` 方法，在每 tick 结束后调用分数评估**

在 `execute()` 方法中，在轻量存活检查之后添加分数评估调用：
```python
async def execute(self, current_tick: int) -> None:
    # 执行轻量存活检查（若离场则内部处理 -10 分）
    if await self._check_life_status_lightweight(current_tick):
        return

    # ===== 新增：每 tick 评估分数贡献 =====
    await self._evaluate_score_contribution(current_tick)

    # 以下逻辑与 deduction 相同（check replan, full reflect）...
    current_hour = current_tick % 12
    if current_hour < 11:
        should_replan, replan_reason = await self._should_replan(current_tick)
        if should_replan:
            await self._replan_remaining(current_tick, replan_reason)

    if (current_tick + 1) % 12 == 0:
        try:
            await self._summarize_short_term_memory(current_tick)
            if await self._check_life_status(current_tick):
                return
            await self._check_long_task_completion(current_tick)
            await self._adjust_long_task(current_tick)
        except Exception as e:
            logger.error(f"[{self.agent_id}][{current_tick}] Full reflect error: {e}")
```

- [ ] **Step 4: 添加 `_evaluate_score_contribution()` 方法**

在文件中添加此完整方法（在 `_summarize_short_term_memory` 之前）：

> **注意：** `RedisKVAdapter` 提供 `incr(key, amount)` 方法（支持负值），以及 `push(key, *values, left=True)` 方法。
> `ltrim` 需通过底层 `self.redis._client.ltrim()` 调用。

```python
async def _evaluate_score_contribution(self, current_tick: int) -> None:
    """
    每 tick 评估该 agent 的行动对复兴大观园稳定度的影响，
    通过 RedisKVAdapter.incr() 原子更新全局 story:score。
    """
    if not self.model or not self.redis:
        return

    try:
        state_component = self._component.agent.get_component("state")
        state_plugin = state_component.get_plugin()

        # 读取本 tick 的行动描述
        current_action = await state_plugin.get_state('current_action')
        if not current_action:
            return  # 无行动记录，跳过

        prompt = f"""你是大观园复兴稳定度的评判官。请根据以下人物的行动，判断这个行动对复兴大观园的贡献。

复兴大观园目标：修缮大观园建筑、聚拢人心、恢复往日诗意与繁荣。

人物：{self.agent_id}
本轮行动：{current_action}

加分情形（+10分）：
1. 主动修缮或建设大观园的建筑、花园、设施
2. 引入外部资源、资金、物资或有力人脉支持园内复兴
3. 成功化解园内人物之间的重大矛盾或冲突
4. 组织集体活动（诗社、宴会、节庆、雅集等）以提振园内士气
5. 招募、培养或说服有才能的人加入复兴事业

减分情形（-10分）：
1. 在园内挑起或激化重大冲突、斗争
2. 泄露园内机密、背叛同伴或破坏信任关系
3. 大量消耗家族资源而无任何实质收益
4. 故意挑拨家族内部关系导致分裂或离心
5. 主动阻止、破坏他人的复兴行动

中性情形（0分）：
- 日常休息、散步、读书、饮茶等不直接影响复兴的行为

判断要求：
- 若行动明确符合某条加分/减分情形，才返回 +10 或 -10
- 若行动影响较小或无关，返回 0
- 每次只返回一个分值

仅返回以下格式之一（不含任何其他文字）：
+10 | 原因（15字以内）
-10 | 原因（15字以内）
0 | 原因（15字以内）"""

        result = await self.model.chat(prompt)
        result = result.strip()

        # 解析结果
        delta = 0
        reason = ''
        if result.startswith('+10'):
            delta = 10
            parts = result.split('|', 1)
            reason = parts[1].strip() if len(parts) > 1 else '有益于复兴'
        elif result.startswith('-10'):
            delta = -10
            parts = result.split('|', 1)
            reason = parts[1].strip() if len(parts) > 1 else '不利于复兴'
        else:
            return  # 0分不需要更新

        # 原子更新 Redis 分数（RedisKVAdapter.incr 支持负数 amount）
        await self.redis.incr('story:score', amount=delta)

        # 记录事件到 Redis list，供前端展示
        # push() 默认 left=True (lpush)；ltrim 需用底层 _client
        event = json.dumps({
            'tick': current_tick,
            'agent': self.agent_id,
            'delta': delta,
            'reason': f'{self.agent_id}：{reason}'
        }, ensure_ascii=False)
        await self.redis.push('story:score_events', event, left=True)
        if self.redis._client:
            await self.redis._client.ltrim('story:score_events', 0, 99)

        logger.info(f"[{self.agent_id}][{current_tick}] Score delta: {delta:+d} | {reason}")

    except Exception as e:
        logger.error(f"[{self.agent_id}][{current_tick}] Score evaluation error: {e}")
```

- [ ] **Step 5: 修改 `_check_life_status_lightweight()` — 角色离场时扣分**

在 `_check_life_status_lightweight` 方法中，找到标记 `已离场` 后的代码块，在 `await state_plugin.set_active_status(False, reason)` 之后，立即插入扣分逻辑：

```python
# 角色离场：稳定度 -10
if self.redis:
    try:
        await self.redis.incr('story:score', amount=-10)
        event = json.dumps({
            'tick': current_tick,
            'agent': self.agent_id,
            'delta': -10,
            'reason': f'{self.agent_id}已离场：{reason[:20]}'
        }, ensure_ascii=False)
        await self.redis.push('story:score_events', event, left=True)
        if self.redis._client:
            await self.redis._client.ltrim('story:score_events', 0, 99)
        logger.info(f"[{self.agent_id}][{current_tick}] Departure penalty: -10 (story:score)")
    except Exception as se:
        logger.warning(f"[{self.agent_id}] Failed to apply departure penalty: {se}")
```

- [ ] **Step 6: Commit**

```bash
git add examples/story/plugins/agent/reflect/BasicReflectPlugin.py
git commit -m "feat(story): add score evaluation logic in ReflectPlugin for revival stability"
```

---

## Task 7: 修改 InvokePlugin — 限制 user_plan 仅对玩家角色有效

**Files:**
- Create: `examples/story/plugins/agent/invoke/BasicInvokePlugin.py`

- [ ] **Step 1: 复制基础文件**

```bash
cp examples/story_of_the_stone/plugins/agent/invoke/BasicInvokePlugin.py \
   examples/story/plugins/agent/invoke/BasicInvokePlugin.py
```

- [ ] **Step 2: 修改 user_plan 处理逻辑**

在 `BasicInvokePlugin.execute()` 方法中，找到检查 `user_plan_key` 的代码块（大约在原文件第71行），将：
```python
user_plan_key = f"user_plan:{self.agent_id}"
user_plan_data_str = await self.redis.get(user_plan_key)
if user_plan_data_str:
```

替换为：
```python
user_plan_key = f"user_plan:{self.agent_id}"
user_plan_data_str = None

# 剧情模式：只有玩家角色才接受 user_plan 干预
player_char_raw = await self.redis.get('story:player_character')
if player_char_raw:
    try:
        import json as _json
        player_char_id = _json.loads(player_char_raw).get('id') if isinstance(player_char_raw, str) else player_char_raw.get('id')
        if player_char_id == self.agent_id:
            user_plan_data_str = await self.redis.get(user_plan_key)
    except Exception as _e:
        logger.warning(f"[{self.agent_id}] Failed to check player character: {_e}")

if user_plan_data_str:
```

- [ ] **Step 3: Commit**

```bash
git add examples/story/plugins/agent/invoke/BasicInvokePlugin.py
git commit -m "feat(story): restrict user_plan intervention to player character only"
```

---

## Task 8: run_simulation.py — 分数初始化、广播与胜负检测

**Files:**
- Create: `examples/story/run_simulation.py`

- [ ] **Step 1: 复制基础文件并修改路径**

```bash
cp examples/story_of_the_stone/run_simulation.py examples/story/run_simulation.py
sed -i '' 's/examples\.deduction/examples.story/g' examples/story/run_simulation.py
```

- [ ] **Step 2: 修改项目路径和端口设置**

在文件中找到 `os.environ["MAS_PROJECT_REL_PATH"]`，改为：
```python
os.environ["MAS_PROJECT_REL_PATH"] = "examples.story"
```

找到 `server_config` 中的端口，改为 `8001`（已在 simulation_config.yaml 中配置，通过 api_cfg 读取）。

- [ ] **Step 3: 在 `main()` 函数中准备 Redis 客户端与故事分数**

在 `await sim_builder.init()` 之后、`server_thread.start()` 之后（等服务器 lifespan 的 `flushdb` 执行完毕），添加：

```python
# 等待 FastAPI server lifespan 完成（含 flushdb），给 0.5 秒缓冲
import time as _time
_time.sleep(1)

# 通过 server_module 暴露的 redis_pool（无下划线前缀）创建 Redis 客户端
import redis.asyncio as _aioredis
import agentkernel_distributed.mas.interface.server as server_module
_story_redis = _aioredis.Redis(connection_pool=server_module.redis_pool)

# 初始化故事分数（在 lifespan flushdb 之后）
await _story_redis.set('story:score', 50)
await _story_redis.delete('story:score_events')
logger.info("【Story】Initialized story:score = 50")
```

> **关键点：** server.py 的 `lifespan` 在 FastAPI 启动时调用 `flushdb()`，所以分数初始化必须在服务器线程启动 **之后** 执行，并留出足够时间让 lifespan 完成。redis_pool 变量名为 `server_module.redis_pool`（无下划线）。

- [ ] **Step 4: 在每 tick 的广播逻辑中加入分数数据**

找到 `await broadcast_tick_data(current_tick, agents_data)` 调用，**在其之后**追加分数广播：

```python
# 原有广播（不修改签名）
await broadcast_tick_data(current_tick, agents_data)

# ===== 追加广播：故事稳定度 =====
import json as _json

# 读取并钳制分数
story_score_raw = await _story_redis.get('story:score')
story_score = int(story_score_raw or 50)
story_score = max(0, min(100, story_score))
await _story_redis.set('story:score', story_score)  # 回写钳制后的值

# 读取本 tick 产生的事件（最多10条）
raw_events = await _story_redis.lrange('story:score_events', 0, 9)
score_events = []
for ev_raw in raw_events:
    try:
        ev = _json.loads(ev_raw)
        if ev.get('tick') == current_tick:
            score_events.append(ev)
    except Exception:
        pass

# 用 server_module.manager（ConnectionManager）直接广播分数消息
score_payload = _json.dumps({
    'type': 'story_score_update',
    'story_score': story_score,
    'score_events': score_events
}, ensure_ascii=False)
await server_module.manager.broadcast(score_payload)

# ===== 胜负检测 =====
if story_score >= 100:
    logger.info("【Story】Victory! story:score >= 100. Stopping simulation.")
    break
elif story_score <= 0:
    logger.info("【Story】Defeat. story:score <= 0. Stopping simulation.")
    break
```

> **注意：** `broadcast_tick_data` 签名为 `(tick, agents_data)` 不接受额外参数。分数通过独立的 `server_module.manager.broadcast()` 以 `type: "story_score_update"` 消息发出，前端监听此消息类型。

- [ ] **Step 5: 在 FastAPI app 上注册 story 专用端点（`set_player_character`）**

在 `import agentkernel_distributed.mas.interface.server as server_module` 之后（`start_server` 调用之前），注册路由：

```python
from fastapi import Request as _Request
import json as _json_ep

@server_module.app.post("/story/set_player")
async def set_player_character(request: _Request):
    """游戏开始时存储玩家角色到 Redis，供 InvokePlugin 校验"""
    data = await request.json()
    if server_module.redis_pool:
        rc = _aioredis.Redis(connection_pool=server_module.redis_pool)
        await rc.set('story:player_character', _json_ep.dumps(data, ensure_ascii=False))
    return {"status": "ok"}
```

> **注意：** FastAPI 允许在 app 运行前注册路由；此路由在 uvicorn 线程启动后生效。
> **"下达任务"不需要新端点**：server.py 已有 WebSocket `set_plan` 消息处理器，前端直接通过 WebSocket 发送 `{type: "set_plan", agent_id, action, target, location}` 即可，无需新 REST API。

- [ ] **Step 6: Commit**

```bash
git add examples/story/run_simulation.py
git commit -m "feat(story): add run_simulation with score init, broadcast, win/lose detection, and task API"
```

---

## Task 9: 端到端验证

- [ ] **Step 1: 验证游戏完整流程**

```bash
cd /Users/hongyuecheng/python-learn/OpenStory
python -m examples.story.run_simulation
```

访问 `http://localhost:8001/frontend/character_select.html`，验证：
1. 角色选择界面正常显示28个角色 + 自定义
2. 选择角色后点击"开始复兴大业"跳转到 index.html
3. index.html 左上角显示玩家角色头像和名字
4. 右侧目标面板显示"稳定度：50/100"
5. "下达任务"弹窗可正常提交
6. Tick 推进后，目标面板分数会根据 NPC 行动变化
7. 分数达到 100 显示胜利界面，跌至 0 显示失败界面

- [ ] **Step 4: Commit**

```bash
git add examples/story/
git commit -m "feat(story): complete story mode revival - integration and verification"
```

---

## 自检

### 规格覆盖

| 需求 | 实现 Task |
|------|----------|
| 角色选择界面，显示所有红楼梦人物 + 孙悟空 + 自定义 | Task 2, 3 |
| 角色有头像（sprite）和信息卡片（家族/性格/背景） | Task 2, 3 |
| 主游戏 UI：玩家角色区（头像/名字/下达任务/跳过） | Task 4, 5 |
| 主游戏 UI：地图区（与 deduction 对齐） | Task 4 |
| 主游戏 UI：目标面板（分数/进度条/历史事件） | Task 4, 5 |
| 分数系统：初始50，±10，100胜，0败 | Task 6, 8 |
| 固定规则：角色离场 -10 | Task 6 Step 5 |
| LLM 判断：每 tick 评估行动贡献 ±10 | Task 6 Step 4 |
| 玩家只能控制自己角色（不能干预 NPC） | Task 7 |
| 分数广播到前端 | Task 8 Step 4 |
| 胜负检测与结局界面 | Task 5, 8 |
| 使用 deduction 地图资源（map/sprite） | Task 1 Step 1 (symlink) |

### Placeholder 扫描
- 无 TBD / TODO / 待实现
- 所有代码块完整
- 所有文件路径精确

### 类型一致性
- `story:score` Redis key 全程统一
- `story:player_character` Redis key 全程统一
- `score_events` 数组中 `{tick, agent, delta, reason}` 格式全程统一
- `user_plan:{agent_id}` key 格式与 deduction 一致
