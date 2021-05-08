import os
import json


def load_enemy_runner(enemy_path, outdir="out"):
    param_group = os.path.basename(os.path.dirname(enemy_path))
    enemy_name, _ = os.path.splitext(os.path.basename(enemy_path))
    # dum
    emodule = getattr(getattr(getattr(__import__(f"{outdir}.enemies.{param_group}.{enemy_name}"), "enemies"), param_group), enemy_name)
    param_path = os.path.join(outdir, "enemies", param_group, f"{enemy_name}.json")
    with open(param_path, "r") as fn:
        parameters = json.load(fn)
        return emodule.Runner, parameters


def run_enemy(runner_class, parameters, iterations=20):
    runner = runner_class(parameters)
    for _ in range(iterations):
        runner._m.reset_logs()
        runner.updateAttack()
        runner._m.print_logs()
        print("=" * 120)


if __name__ == "__main__":
    path = "out/enemies/AGITO_ABS/HBS_0020301_03_Volk.py"
    runner_class, parameters = load_enemy_runner(path)
    print(runner_class)
    run_enemy(runner_class, parameters)
