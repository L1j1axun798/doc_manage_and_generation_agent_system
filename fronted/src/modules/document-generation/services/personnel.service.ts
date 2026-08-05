import { fetchProjectMembers } from '@/modules/projects/api/project-members.api'
import type { ProjectMemberRole } from '@/modules/projects/projects.types'
import type { AvailableAgentPersonnel } from '../document-generation.types'

const roleLabels: Record<ProjectMemberRole, string> = {
  manager: '项目负责人',
  operator: '项目操作人员',
  viewer: '项目查看人员',
}

export async function fetchAvailableAgentPersonnel(
  projectId: number,
): Promise<AvailableAgentPersonnel[]> {
  const members = await fetchProjectMembers(projectId)
  return members.map((member) => ({
    id: String(member.user),
    user_id: member.user,
    project_member_id: member.id,
    name: member.user_real_name || member.user_username,
    job_title: roleLabels[member.role],
    department: '',
    contact: '',
    certifications: [],
    certificate_valid_until: null,
    additional_info: {
      project_role: member.role,
      project_member_id: member.id,
    },
  }))
}
