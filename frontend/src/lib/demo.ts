export const DEMO_ALARMS_CSV = `告警级别,告警名称,设备,端口,定位信息,最近发生时间
紧急,OTS_LOS,N1,N1:N1-N2,0-subrack-16-K1SL16-1(LINE1/LINE2)-OCh,2026/08/11 14:58
紧急,OSC_LOS,N2,N2:N1-N2,0-subrack-16-K1SL16-1(LINE1/LINE2)-OCh,2026/08/11 14:58
重要,OMS_LOS_P,N2,N2:N2-N4,0-subrack-14-TNG1SL64-1(IN1/IN2)-Ch3,2026/08/11 14:58
重要,OCH_LOS_P,N4,N4:N2-N4,0-subrack-14-K1OB1-1(IN1/IN2)-Ch3,2026/08/11 14:58
重要,OMS_LOS_P,N4,N4:N4-N5,0-subrack-15-K1OP1-1(LINE1/LINE2)-Ch4,2026/08/11 14:58
重要,OCH_LOS_P,N5,N5:N4-N5,0-subrack-15-K1SL16-1(LINE1/LINE2)-Ch4,2026/08/11 14:58
重要,OCH_LOS_P,N4,N4:N4-N5,0-subrack-15-K1OP1-1(LINE1/LINE2)-Ch4,2026/08/11 14:58
重要,OMS_LOS_P,N2,N2:N2-N4,0-subrack-9-TNG3SLO1-1(OUT1/OUT2)-Ch5,2026/08/11 14:58
`;

export const DEMO_TOPOLOGY = {
  devices: [
    { device_id: "N1", type: "OADM" },
    { device_id: "N2", type: "OXC" },
    { device_id: "N3", type: "OADM" },
    { device_id: "N4", type: "OADM" },
    { device_id: "N5", type: "OXC" },
  ],
  ports: [
    { port_id: "N1:N1-N2", device_id: "N1", direction: "out" },
    { port_id: "N2:N1-N2", device_id: "N2", direction: "in" },
    { port_id: "N1:N1-N4", device_id: "N1", direction: "out" },
    { port_id: "N4:N1-N4", device_id: "N4", direction: "in" },
    { port_id: "N2:N2-N3", device_id: "N2", direction: "out" },
    { port_id: "N3:N2-N3", device_id: "N3", direction: "in" },
    { port_id: "N2:N2-N4", device_id: "N2", direction: "out" },
    { port_id: "N4:N2-N4", device_id: "N4", direction: "in" },
    { port_id: "N4:N4-N5", device_id: "N4", direction: "out" },
    { port_id: "N5:N4-N5", device_id: "N5", direction: "in" },
  ],
  links: [
    { link_id: "N1-N2", endpoint_a: "N1:N1-N2", endpoint_b: "N2:N1-N2", length_km: 10 },
    { link_id: "N1-N4", endpoint_a: "N1:N1-N4", endpoint_b: "N4:N1-N4", length_km: 10 },
    { link_id: "N2-N3", endpoint_a: "N2:N2-N3", endpoint_b: "N3:N2-N3", length_km: 10 },
    { link_id: "N2-N4", endpoint_a: "N2:N2-N4", endpoint_b: "N4:N2-N4", length_km: 10 },
    { link_id: "N4-N5", endpoint_a: "N4:N4-N5", endpoint_b: "N5:N4-N5", length_km: 10 },
  ],
};

export function createDemoDiagnoseForm(): FormData {
  const blob = new Blob([DEMO_ALARMS_CSV], { type: "text/csv" });
  const file = new File([blob], "alarm1.csv", { type: "text/csv" });
  const form = new FormData();
  form.append("alarms", file);
  form.append("topology", JSON.stringify(DEMO_TOPOLOGY));
  return form;
}

export async function runDemoDiagnose(): Promise<Response> {
  const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8010";
  return fetch(`${API_URL}/api/v1/diagnose`, {
    method: "POST",
    body: createDemoDiagnoseForm(),
  });
}
