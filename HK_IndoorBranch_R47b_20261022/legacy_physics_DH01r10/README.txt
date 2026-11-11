DH01-r10历史局部物理验证材料。包含335项静态碰撞、10个铰链、13个道具及注册变换；不是全城物理运行器，也不是UE快照系统。
复验时先把整个此目录复制到独立工作目录，再使用Node运行 node verify_registered.mjs。它会在自己的目录写 registered_physics_verification.json。
Rapier实现为既有打包版本，随rapier.mjs附带；不要替换为最新库后仍引用原结果。验证只涉及manifest中的局部对象/路径；不等于机器人已执行任务。
