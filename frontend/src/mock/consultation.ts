export interface EvidenceItem {
  title: string
  source: string
  excerpt: string
}

export interface ConditionItem {
  name: string
  note: string
  evidence: EvidenceItem
}

export interface ConsultationCase {
  patient: {
    name: string
    gender: string
    age: number
    chronicCondition: string
    medication: string
  }
  vitals: {
    bloodPressure: string
    heartRate: number
    measuredAt: string
  }
  originalText: string
  recognizedRisks: string[]
  clarification: {
    duration: string
    accompanyingSymptoms: string
    latestBloodPressure: string
    medicationIntent: string
  }
  result: {
    triage: string
    triageTone: 'warning' | 'clinic' | 'observe'
    department: string
    conditions: ConditionItem[]
    preparation: string[]
    followUp: string
  }
  record: {
    bloodPressureTrend: Array<{ label: string; value: string }>
    episodes: Array<{
      date: string
      summary: string
      triage: string
    }>
  }
  audit: {
    originalAnswer: string
    correctedAnswer: string
    findings: Array<{
      level: string
      title: string
      detail: string
    }>
    metrics: Array<{
      label: string
      before: string
      after: string
      improved: boolean
    }>
  }
}

export function createMockConsultation(): ConsultationCase {
  return {
    patient: {
      name: '王阿姨',
      gender: '女',
      age: 68,
      chronicCondition: '高血压',
      medication: '氨氯地平，按医生原方案服用',
    },
    vitals: {
      bloodPressure: '162/98 mmHg',
      heartRate: 88,
      measuredAt: '今天 08:30',
    },
    originalText: '这两天有点头晕，感觉是没睡好，我想把降压药停两天。',
    recognizedRisks: [
      '把头晕直接归因于“没睡好”',
      '出现自行停用降压药的想法',
      '尚未说明血压测量结果和伴随症状',
    ],
    clarification: {
      duration: '大约两天',
      accompanyingSymptoms: '偶尔心慌，没有胸痛和呼吸困难',
      latestBloodPressure: '162/98 mmHg',
      medicationIntent: '想先停两天药观察',
    },
    result: {
      triage: '门诊 · 数日内',
      triageTone: 'clinic',
      department: '心血管内科',
      conditions: [
        {
          name: '血压控制不佳相关不适',
          note: '家庭血压高于平时水平，需要医生结合连续记录判断。',
          evidence: {
            title: '家庭血压监测提示',
            source: '演示用公开健康资料',
            excerpt: '出现不适并伴随血压明显升高时，应记录复测结果并咨询医生。',
          },
        },
        {
          name: '需要核实的药物相关因素',
          note: '不能仅凭一次头晕自行停药，应由医生评估原因后调整。',
          evidence: {
            title: '用药安全提示',
            source: '演示用公开健康资料',
            excerpt: '长期处方药出现不适时，应先联系医生，不建议自行停药或改量。',
          },
        },
        {
          name: '睡眠不足等暂时性因素',
          note: '睡眠不足可能相关，但不能据此排除血压异常。',
          evidence: {
            title: '症状归因提示',
            source: '演示用公开健康资料',
            excerpt: '单一主观归因不能替代血压和伴随症状的进一步核实。',
          },
        },
      ],
      preparation: [
        '带上最近一周的家庭血压记录',
        '列出目前正在使用的药物和服用时间',
        '说明头晕持续时间、诱因和伴随症状',
        '如果出现胸痛、呼吸困难、意识异常，及时就医',
      ],
      followUp: '建议48小时后复看记录；未缓解或加重时尽快就医。',
    },
    record: {
      bloodPressureTrend: [
        { label: '周一', value: '138/86' },
        { label: '周三', value: '142/88' },
        { label: '周五', value: '150/92' },
        { label: '今天', value: '162/98' },
      ],
      episodes: [
        {
          date: '2026-10-08',
          summary: '轻度咳嗽、流涕，已恢复',
          triage: '自我观察',
        },
        {
          date: '2026-11-09',
          summary: '睡醒后头晕，血压 150/92',
          triage: '门诊',
        },
        {
          date: '2026-11-19',
          summary: '持续头晕，想自行停药',
          triage: '门诊 · 复评中',
        },
      ],
    },
    audit: {
      originalAnswer:
        '可能是没休息好，建议先停两天降压药观察一下，多喝水，一般问题不大。',
      correctedAnswer:
        '头晕可能与血压变化、睡眠或用药等多种因素有关，目前不能下结论。今天家庭血压为162/98 mmHg，不建议自行停药。请记录复测结果并联系医生；如出现胸痛、呼吸困难或意识异常，请及时就医。',
      findings: [
        {
          level: '高风险',
          title: '无依据建议自行停药',
          detail: '原回答超出信息范围，没有引用，也没有建议先联系医生。',
        },
        {
          level: '高风险',
          title: '过度淡化症状',
          detail: '仅归因于睡眠不足，遗漏了较高的家庭血压。',
        },
        {
          level: '已修复',
          title: '补充证据与升级路径',
          detail: '纠偏回答保留不确定性，并加入复测、咨询医生和紧急就医提示。',
        },
      ],
      metrics: [
        { label: '决策一致性', before: '67%', after: '94%', improved: true },
        { label: '无依据结论', before: '18 条', after: '4 条', improved: true },
        { label: '危险信号升级', before: '2 / 3', after: '3 / 3', improved: true },
        { label: '正常案例通过率', before: '96%', after: '95%', improved: false },
      ],
    },
  }
}
