import inspect
import logging

from lnst.Controller import Controller
from lnst.Controller.ContainerPoolManager import ContainerPoolManager
from lnst.Controller.MachineMapper import ContainerMapper
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.BondingMixin import BondingMixin
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import OffloadSubConfigMixin

import lnst.Recipes.ENRT as enrt_recipes

podman_uri = "unix:///run/podman/podman.sock"
image_name = "lnst"

params_base = dict(
    perf_tests=['tcp_stream'],
    perf_duration=5,
    perf_iterations=2,
    perf_warmup_duration=0,
    ping_count=1,
    perf_test_simulation=True,
)

i = 0
recipe_results = {}
for recipe_name in dir(enrt_recipes):
    if recipe_name in ["BaseEnrtRecipe", "BaseTunnelRecipe", "BaseLACPRecipe", "DellLACPRecipe"]:
        continue

    if "Ovs" in recipe_name or "OvS" in recipe_name:
        continue

    recipe = getattr(enrt_recipes, recipe_name)

    if not (inspect.isclass(recipe) and issubclass(recipe, BaseEnrtRecipe)):
        continue

    i += 1
    if recipe_name == "DoubleTeamRecipe":
        continue

    params = params_base.copy()

    if issubclass(recipe, BondingMixin) or recipe_name == "GreTunnelOverBondRecipe":
        params["bonding_mode"] = "active-backup"
        params["miimon_value"] = 5
    elif issubclass(recipe, enrt_recipes.TeamRecipe) or issubclass(recipe, enrt_recipes.DoubleTeamRecipe):
        params["runner_name"] = "activebackup"
    elif recipe_name.startswith("CT"):
        del params["perf_tests"]
        if "CTFulltableInsertionRateRecipe" in recipe_name:
            params["long_lived_conns"] = 10000
    elif recipe_name == "SoftwareRDMARecipe":
        del params["perf_tests"]
    elif recipe_name == "ShortLivedConnectionsRecipe":
        del params["perf_tests"]

    if recipe_name in ["GeneveLwtTunnelRecipe", "GreLwtTunnelRecipe", "L2TPTunnelRecipe", "VxlanLwtTunnelRecipe", "GeneveTunnelRecipe", "VxlanGpeTunnelRecipe"]:
        params["carrier_ipversion"] = "ipv4"

    if recipe_name in ["SitTunnelRecipe", "IpIpTunnelRecipe", "Ip6TnlTunnelRecipe"]:
        params["tunnel_mode"] = "any"

    if issubclass(recipe, OffloadSubConfigMixin):
        params['offload_combinations'] = []

    try:
        recipe_instance = recipe(**params)

        print(f"-----------------------------{recipe_name} {i}START---------------------------")
        ctl = Controller(
            poolMgr=ContainerPoolManager,
            mapper=ContainerMapper,
            podman_uri=podman_uri,
            image=image_name,
            debug=1,
            network_plugin="custom_lnst"
        )
        ctl.run(recipe_instance)

        overall_result = all([run.overall_result for run in recipe_instance.runs])
        recipe_results[recipe_name] = "PASS" if overall_result else "FAIL"
    except Exception as e:
        logging.exception(f"Recipe {recipe_name} crashed with exception.")
        recipe_results[recipe_name] = f"EXCEPTION: {e}"

print("Recipe run results:")
for recipe_name, result in recipe_results.items():
    print(recipe_name, result)

exit(not all(recipe_results.values()))
