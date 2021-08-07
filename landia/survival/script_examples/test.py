
from landia import gamectx
from landia.survival.survival_content import GameContent

content:GameContent = self
def test_trigger(source_obj):
    print("HERE")
    return True

for obj in gamectx.object_manager.get_objects_by_config_id("monster1"):
    print(obj.get_id())
    obj.add_trigger("unarmed_attack", "test", test_trigger)
    print("ADDED TRIGGER")


content.log_console("HI to console")

print("hi")



