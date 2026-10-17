/** Privacy-reduced, descriptive backend cluster details only. */
export function clusterDetailsText(properties) {
  const rows = [`Cluster ${properties.clusterId ?? 'identifier unavailable'}`, 'Exploratory ST-DBSCAN grouping']
  if (Number.isFinite(Number(properties.memberCount)) && properties.memberCount != null) rows.push(`${properties.memberCount} case/source records`)
  if (Number.isFinite(Number(properties.supportCount)) && properties.supportCount != null) rows.push(`${properties.supportCount} distinct farms/supports`)
  if (properties.startDate && properties.endDate) rows.push(`Observed ${properties.startDate} to ${properties.endDate}`)
  if (properties.asOf) rows.push(`Analysis as of ${properties.asOf}`)
  rows.push('Descriptive grouping; no future infections or transmission route is inferred.')
  return rows.join('\n')
}
