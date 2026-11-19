export const title = "tabletop run lifecycle (after prepare)";

export const state = (v) => {
  if (v.finished) return "完成，报告已写";
  if (v.pc === "open") return "读取事件日志";
  if (v.pc === "neg") return "负对照进行中";
  if (v.pc === "eng") return "工程回合进行中";
  if (v.pc === "final") return "写最终报告";
  if (v.reportRejected) return "卡住：最终报告写不进";
  if (v.blocked) return "卡住：重跑被已有目录拒绝";
  if (v.invalid) return "整批作废";
  const partial = v.reportOut ? "（已有中途报告）" : "";
  if (v.charges === 0 && v.dirs.length === 0) return "已 prepare，未开跑" + partial;
  return "中断，等待重跑" + partial;
};

export const group = (v) => {
  if (v.finished) return "done";
  if (v.pc !== "idle") return "running";
  if (v.reportRejected || v.blocked) return "stuck";
  if (v.invalid) return "void";
  return "waiting";
};

export const colors = { done: "teal", running: "blue", stuck: "orange", void: "pink", waiting: "tan" };

const labels = {
  OperatorRunsKernel: "你运行 kernel",
  OperatorRunsReport: "你单独运行 report",
  Interrupted: "进程被中断",
  NegDirExists: "回合目录已存在，报错",
  ExecDirExists: "回合目录已存在，报错",
  NegLoopDone: "负对照都通过",
  BudgetSpent: "物理预算用完",
  WaitRejected: "等待动作被拒，整批作废",
  NegativeSatisfiesGoal: "负对照满足了目标",
  InterruptedEpisodeVoids: "发现中断的回合，整批作废",
  BatchAlreadyVoid: "已作废，停止",
  LogIsClean: "事件日志干净，继续",
  InitialStateMismatch: "初态哈希不符",
  SystemExecutionFailure: "系统执行错误",
  RowsDone: "所有行跑完",
  FinalReportWritten: "报告写入",
  FinalReportRefused: "报告与已有的不同，拒写",
  Done: "结束",
};

// Steps inside one negative() or one row share one label; they draw as a self-loop.
export const step = (action) => labels[action] ?? "回合内推进";
