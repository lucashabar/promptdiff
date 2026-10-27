# promptdiff

**逐行比对两次提示词的改动。**

`promptdiff` —— 按语义块比对两版提示词，区分措辞调整、约束增删与结构变动。

- 零依赖，Python 3.10+ 标准库即可运行
- 单文件，`promptdiff.py` 拷走就能用
- 不联网、不写文件

<!-- ipos:install -->
## 安装

零依赖，Python 3.10+ 即可：

```bash
pip install lucashabar-promptdiff
```

装完直接用命令名调用：

```bash
promptdiff --help
```

也可以不用安装，直接把 `promptdiff.py` 拷走用——它只依赖标准库。

## 为什么需要它

普通 diff 看不懂提示词改动的后果；promptdiff 按语义块归类，并把约束的增删单独标出来。

它遵守下面几条自己定的规矩：

1. **看语义块，不看行号**。普通 diff 会告诉你第 40 行换了个词，不会告诉你「这一句把允许范围收窄了」。
2. **约束增删要单独拎出来**。改措辞和改规则不是一回事。
3. **不自动合并**。这是给人看的审阅工具。

## 用法

```bash
python promptdiff.py --old v1.txt --new v2.txt
python promptdiff.py --old v1.txt --new v2.txt --json
```

加 `--json` 可以拿到机器可读的结果，便于接到流水线里。

## 已知局限

- 改动分类基于关键词与相似度，判断不了「改得对不对」。
- 只做对比，不自动合并，也不生成新版本。
- 块切分规则简单，复杂的嵌套结构可能被切碎。

## 跑测试

```bash
python test_promptdiff.py
```

测试用独立的断言与临时数据，不污染工作目录。

## 来源与参考

- Python 标准库文档：<https://docs.python.org/3/>
- GitHub 仓库：<https://github.com/lucashabar/promptdiff>

---

## 关于作者

lucashabar 做提示词变更审阅相关的问题。这个工具先替你回答一个具体问题，再谈别的。

- 个人主页：<https://lucashabar.github.io>
- 仓库：<https://github.com/lucashabar/promptdiff>

## 许可

MIT，见 [LICENSE](LICENSE)。
