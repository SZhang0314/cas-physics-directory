# 中国科学院物理相关院所 · 师资检索 / CAS Physics Institutes Faculty Directory

一个自包含的网页，收录**中国科学院 6 个物理相关院所 1490 位科研教师/研究人员**，支持按单位、关键词搜索与筛选，每人卡片链接到其官方个人主页。

数据来源：各研究所官方网站的教师/研究人员名录与个人主页，抓取于 2026-10-01。
每条记录均可溯源（`sources` 字段记录实际使用的 URL）。

## 网页功能

- 按**姓名 / 研究方向 / 研究重点 / 论文 / 简介**全文搜索
- 按**单位（6 个）**筛选，**级联的部门筛选**（选定单位后，部门下拉仅显示该单位下属部门）
- 按**姓名 / 单位 / 职称**排序
- 每张卡片显示：职称、所属部门、研究方向、研究简介、代表性论文、个人主页/邮箱链接

> 部门筛选说明：中科院近代物理研究所（375 人，按研究中心/学科）与精密测量科学与技术创新研究院
> （293 人，按研究部）提供部门数据；物理所、高能所、理论物理所、上海应物所官方名录未提供部门字段，
> 选择这些单位时部门下拉自动禁用。所有部门名称均为中文规范名称，不含英文代码。

## 目录结构

```
cas-physics-directory/
├── data/
│   ├── faculty.json        # 数据源（每人一条记录，fine/coarse）
│   ├── roster_coarse.json  # Pass1 粗名单
│   └── raw/                # 抓取缓存（名录页、详情页）
├── scrape_roster.py        # Pass1：抓取各所名录
├── enrich.py               # Pass2：抓取并解析个人主页
├── fix_ids.py              # 规范化 id 为 ASCII slug
├── clean_departments.py    # 将 APM 部门代码映射为中文名
├── add_summaries.py        # 为每位教师补齐简介（真实简历优先，否则按字段合成）
├── finalize.py             # 补充 subject 字段
├── assets/site_template.html  # 网页模板（含级联筛选逻辑）
├── index.html              # 自包含网页（内嵌数据 + CSS/JS）
├── README.md
└── .nojekyll
```

## 数据统计

| 单位 | 人数 | fine | 有研究方向 | 有邮箱 | 有论文 |
|---|---|---|---|---|---|
| 中国科学院物理研究所 | 457 | 457 | 300 | 447 | 275 |
| 中国科学院近代物理研究所 | 375 | 365 | 375 | 361 | 0 |
| 中国科学院精密测量科学与技术创新研究院（原武汉物数所） | 293 | 281 | 221 | 262 | 96 |
| 中国科学院高能物理研究所 | 167 | 158 | 138 | 148 | 28 |
| 中国科学院上海应用物理研究所 | 130 | 0 | 0 | 0 | 0 |
| 中国科学院理论物理研究所 | 68 | 63 | 63 | 63 | 0 |
| **合计** | **1490** | **1324** | **1097** | **1281** | **399** |

- 论文条目合计：1832 条；**研究简介：1490 人全覆盖**。
  - 其中约 1265 人简介来自个人主页的真实简介/简历字段；
  - 其余记录（含上海应物所仅名录的 130 人）由**已核实的字段**（职称/部门/研究方向）合成一句话简介，不含虚构信息。
- `confidence`：`fine` 表示已抓取个人主页并补充研究方向/简介/邮箱；`coarse` 表示仅名录级信息。

## 各所数据来源与说明

| 单位 | 名录来源 | 个人主页 |
|---|---|---|
| 物理所 IPhy | `in.iphy.ac.cn/list_json.php?t={zgjgwry,tpyjy,yjdwfgj}` | 同接口 `&id=NNN`（含方向/简介/论文/邮箱） |
| 高能所 IHEP | `ihep.cas.cn/kydw/{yjy,tpyjy}/index_N.html` | `sourcedb_ihep_cas` 专家页 |
| 理论物理所 ITP | `itp.cas.cn/rc/{yjtd,ys,jcqn,rxry}/` | `/sourcedb/zw/zjrck/...` |
| 近代物理所 IMP | `imp.cas.cn/edu/zsyds/ds/dsyjzx/`（导师目录，含中心/学科） | `people.ucas.ac.cn/~<slug>`（UCAS 主页） |
| 上海应物所 SINAP | `sinap.cas.cn/rcdw/kjgg/`（科技骨干名单） | **无个人详情页**（站点名录仅为展示文本，无链接） |
| 精密测量院 APM（原武汉物数所） | `apm.cas.cn/rcdw/{zgj,fgj}/`（按研究部分组） | `/sourcedb/zw/rck/...` 专家页 |

**说明：**
- 上海应用物理研究所官网的科技骨干名录为纯文本展示、无个人主页链接，故该所 130 人保持 `coarse`。
- 武汉物理与数学研究所已并入中国科学院精密测量科学与技术创新研究院（APM），故以 APM 为准。
- 部分主页未公开论文或简介栏目，故相关字段非全员覆盖。
- 少数同名人员为不同个体（主页 URL 不同），已按 `(单位,姓名,主页)` 去重。

## 重新生成

```bash
python scrape_roster.py            # Pass1 抓取名录（有缓存）
python enrich.py                   # Pass2 抓取个人主页并填充字段
python fix_ids.py                  # 规范化 id
python clean_departments.py        # 部门代码 -> 中文名
python add_summaries.py            # 补齐每位教师的简介
python finalize.py                 # 补充 subject
python <search_prof>/scripts/validate_data.py --data data/faculty.json
python <search_prof>/scripts/build_site.py --data data/faculty.json --out . \
  --template assets/site_template.html \
  --title "中国科学院物理相关院所 · 师资检索 / CAS Physics Institutes Faculty Directory"
```

## 说明

- 数据仅包含公开信息（官网名录、个人主页公开简介与论文列表）。
- 记录字段：`id, name, school, department, title, subject, research_directions, focus_areas, summary, publications, homepage, profile_url, email, sources, confidence, verified`。
- 所有记录均附 `sources`（实际使用的 URL）以便审计。
