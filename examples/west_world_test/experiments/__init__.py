"""论文级长 tick 仿真实验工具包。

- `metrics.py`：纯函数指标提取层（解析 run 输出，无 Ray 依赖，可单测）。
- `overseer_dynamics.py`：批量编排层（参数矩阵 × subprocess 跑 run_simulation + 聚合）。
"""
