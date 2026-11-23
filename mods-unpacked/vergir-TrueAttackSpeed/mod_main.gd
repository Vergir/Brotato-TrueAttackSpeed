extends Node

const MOD_ID := "vergir-TrueAttackSpeed"
const LOG_NAME := "vergir-TrueAttackSpeed:Main"


# Installs the script extensions.
func _init() -> void :
	var extensions_dir: String = ModLoaderMod.get_unpacked_dir().plus_file(MOD_ID).plus_file("extensions")

	ModLoaderMod.install_script_extension(extensions_dir.plus_file("weapons/shooting_behaviors/ranged_weapon_shooting_behavior.gd"))
	ModLoaderMod.install_script_extension(extensions_dir.plus_file("weapons/shooting_behaviors/melee_weapon_shooting_behavior.gd"))
	# Whip and Flail. The Boomerang must not get an extension of its own (docs/architecture.md).
	ModLoaderMod.install_script_extension(extensions_dir.plus_file("weapons/shooting_behaviors/animated_hitbox_shooting_behavior.gd"))
	ModLoaderMod.install_script_extension(extensions_dir.plus_file("entities/structures/turret/turret.gd"))
	# Sits on top of Improved Tooltips' extension of the same script (an optional dependency loads first).
	ModLoaderMod.install_script_extension(extensions_dir.plus_file("ui/menus/shop/item_description.gd"))


func _ready() -> void :
	ModLoaderLog.info("Ready", LOG_NAME)
