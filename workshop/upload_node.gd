extends Node

# Keeps the results of Steam's Workshop calls for workshop/upload.py to read.
var created = null
var updated = null


func _ready() -> void :
	var _a = Steam.connect("item_created", self, "_on_created")
	var _b = Steam.connect("item_updated", self, "_on_updated")


func _on_created(result: int, file_id: int, accept_tos: bool) -> void :
	created = [result, str(file_id), accept_tos]


func _on_updated(result: int, need_to_accept_tos: bool, file_id: int = 0) -> void :
	updated = [result, need_to_accept_tos, str(file_id)]
