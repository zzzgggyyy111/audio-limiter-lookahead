# audio-limiter-lookahead

## 题面

母带加前瞻限幅后，鼓点起音还是破、整体还一抽一抽：包络不做前瞻，起始瞬态漏限；增益曲线用 dB 相减再线性，数值错；attack 与 release 用同一常数，释放太硬；延迟补偿少一个样本，峰值偏移 1；增益应用在延迟前，时间错位；真峰值不做过采样，采样间峰值超限；参数不校验，ceiling>0 时整体压扁；释放时间不钳制，出现泵浦；批量共用包络，轨道之间串；window<=0 不校验，除零。limiter/lookahead.py 是核心，tests/test_lookahead.py 15个红。要修的是：补齐 limiter/lookahead.py 中 8 个函数，消除上述 10 个缺陷，在不修改 tests 的前提下让 15 个测试全部通过。

## 运行方式

在仓库根目录运行：

```powershell
cd D:\gsb-20261119\audio-limiter-lookahead
python -m pytest tests -q
```

初始失败环境必须恰好是：

```text
15 failed
```

输出尾部应为 `15 failed in ...s`，且没有 collection error、import error 或 syntax error。只需要 Python 3 和 pytest；全部离线，无外部依赖、无随机数、无 sleep。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 音视频处理 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 验收基线

`tests/test_lookahead.py` 是验收基线，不得修改、删除或弱化其中任何测试。实现只改 `limiter/lookahead.py`，保持 8 个公开函数的签名、dB/ms 契约、以样本计的窗口与延迟语义以及 `LimiterError` 行为；所有时间常数单位为毫秒，默认绝对容差为 `1e-6`。
