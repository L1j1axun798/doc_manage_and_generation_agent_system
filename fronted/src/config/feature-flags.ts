import { env } from './env'

export const featureFlags = {
  auth: false,
  documentCenter: false,
  projectManagement: false,
  documentAgent: env.documentAgentEnabled,
}
