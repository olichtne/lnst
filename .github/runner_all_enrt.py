import inspect
import logging

from lnst.Controller import Controller
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import OffloadSubConfigMixin

import lnst.Recipes.ENRT as enrt_recipes

podman_uri = "unix:///run/podman/podman.sock"
image_name = "lnst"
ctl = Controller(
    poolMgr=ContainerPoolManager,
    mapper=ContainerMapper,
    podman_uri=podman_uri,
    image=image_name,
    debug=1,
    network_plugin="custom_lnst"
)

params_base = dict(
    perf_tests=['tcp_stream'],
    perf_duration=5,
    perf_iterations=2,
    perf_warmup_duration=0,
    ping_count=1,
    perf_test_simulation=True,
)

recipe_results = {}
for recipe_name in dir(enrt_recipes):
    if recipe_name in ["BaseEnrtRecipe", "BaseTunnelRecipe", "BaseLACPRecipe"]:
        continue

    recipe = getattr(enrt_recipes, recipe_name)

    if not (inspect.isclass(recipe) and issubclass(recipe, BaseEnrtRecipe)):
        continue

    params = params_base.copy()

    if "Bond" in recipe_name:
        params["bonding_mode"] = "active-backup"
        params["miimon_value"] = 5
    elif recipe_name.startswith("CT"):
        del params["perf_tests"]
        if "CTFulltableInsertionRateRecipe" in recipe_name:
            params["long_lived_conns"] = 10000
    elif recipe_name == "SoftwareRDMARecipe":
        del params["perf_tests"]

    if issubclass(recipe, OffloadSubConfigMixin):
        params['offload_combinations'] = []

    try:
        recipe_instance = recipe(**params)

        ctl.run(recipe_instance)

        overall_result = all([run.overall_result for run in recipe_instance.runs])
        recipe_results[recipe_name] = "PASS" if overall_result else "FAIL"
    except Exception as e:
        logging.exception("Recipe crashed with exception.")
        recipe_results[recipe_name] = f"EXCEPTION: {e}"

print("Recipe run results:")
for recipe_name, result in recipe_results.items():
    print(recipe_name, result)

exit(not all(recipe_results.values()))
