/**
 * ViewerContext Contract and Fail-Closed Access Foundation
 *
 * NOTE: Frontend access checks control presentation only.
 * Real authorization must be enforced by the backend after shared authentication integration.
 */

/**
 * Immutable Canonical System Roles
 */
export const ROLES = Object.freeze({
  FARMER: 'FARMER',
  VETERINARY_OFFICER: 'VETERINARY_OFFICER',
  DAPH_OFFICIAL: 'DAPH_OFFICIAL',
});

/**
 * Immutable Canonical Scope Levels
 */
export const SCOPE_LEVELS = Object.freeze({
  FARM: 'FARM',
  DISTRICT: 'DISTRICT',
  PROVINCE: 'PROVINCE',
  NATIONAL: 'NATIONAL',
});

/**
 * Immutable Role-to-Allowed-Scope Matrix
 */
export const ROLE_ALLOWED_SCOPES = Object.freeze({
  [ROLES.FARMER]: Object.freeze([SCOPE_LEVELS.FARM]),
  [ROLES.VETERINARY_OFFICER]: Object.freeze([SCOPE_LEVELS.DISTRICT, SCOPE_LEVELS.PROVINCE]),
  [ROLES.DAPH_OFFICIAL]: Object.freeze([
    SCOPE_LEVELS.DISTRICT,
    SCOPE_LEVELS.PROVINCE,
    SCOPE_LEVELS.NATIONAL,
  ]),
});

/**
 * Immutable Canonical Permissions
 */
export const PERMISSIONS = Object.freeze({
  viewDataQuality: 'viewDataQuality',
  viewModelTransparency: 'viewModelTransparency',
  manageAlerts: 'manageAlerts',
  recordResponse: 'recordResponse',
  viewReports: 'viewReports',
});

/**
 * Screen Status Planning Metadata Constants
 */
export const SCREEN_STATUS = Object.freeze({
  UI_READY_API_BLOCKED: 'UI_READY_API_BLOCKED',
  DEFER: 'DEFER',
});

/**
 * Screen Classification Planning Matrix
 */
export const SCREEN_CLASSIFICATION = Object.freeze({
  FARMER: {
    diseaseRisk: SCREEN_STATUS.UI_READY_API_BLOCKED,
    alertsAndGuidance: SCREEN_STATUS.UI_READY_API_BLOCKED,
  },
  VETERINARY_OFFICER: {
    surveillanceDashboard: SCREEN_STATUS.UI_READY_API_BLOCKED,
    districtForecasts: SCREEN_STATUS.UI_READY_API_BLOCKED,
    surveillanceAndResponse: SCREEN_STATUS.DEFER,
    history: SCREEN_STATUS.DEFER,
  },
  DAPH_OFFICIAL: {
    surveillanceOverview: SCREEN_STATUS.UI_READY_API_BLOCKED,
    districtForecasts: SCREEN_STATUS.UI_READY_API_BLOCKED,
    surveillanceAndAlerts: SCREEN_STATUS.DEFER,
    reportsAndTrends: SCREEN_STATUS.DEFER,
    dataQuality: SCREEN_STATUS.UI_READY_API_BLOCKED,
  },
  CAPABILITY_GATED: {
    // Requires permissions.viewModelTransparency === true. Not a separate user role.
    modelTransparency: SCREEN_STATUS.UI_READY_API_BLOCKED,
  },
});

/**
 * Proposed ViewerContext contract shape.
 *
 * @typedef {Object} ViewerContext
 * @property {string} userId - Unique identifier for the authenticated user.
 * @property {"FARMER" | "VETERINARY_OFFICER" | "DAPH_OFFICIAL"} role - Canonical system role.
 * @property {Object} authorization - User authorization and scoping configuration.
 * @property {"FARM" | "DISTRICT" | "PROVINCE" | "NATIONAL"} authorization.scopeLevel - Scoping tier.
 * @property {string | null} authorization.registeredFarmDistrict - Primary farm district for FARMER role.
 * @property {string[]} authorization.authorizedDistricts - List of administrative districts allowed for viewer.
 * @property {string[]} authorization.assignedFarmIds - List of farm IDs assigned to VETERINARY_OFFICER.
 * @property {Object} permissions - Capability flags for feature presentation gating.
 * @property {boolean} permissions.viewDataQuality - Ability to view data quality & fallback metrics.
 * @property {boolean} permissions.viewModelTransparency - Ability to view model explainability (log-odds, ECE).
 * @property {boolean} permissions.manageAlerts - Ability to manage surveillance alerts.
 * @property {boolean} permissions.recordResponse - Ability to log outbreak responses.
 * @property {boolean} permissions.viewReports - Ability to view aggregate surveillance reports.
 */

/**
 * Pure function to validate and normalize a ViewerContext object.
 * Fails closed on missing, incompatible, or invalid data. Does not mutate the supplied object.
 *
 * @param {Object} viewerContext
 * @returns {{ valid: boolean, reason: string | null, normalizedContext: Object | null }}
 */
export function validateViewerContext(viewerContext) {
  if (!viewerContext || typeof viewerContext !== 'object') {
    return { valid: false, reason: 'ViewerContext must be a non-null object', normalizedContext: null };
  }

  const { userId, role, authorization, permissions } = viewerContext;

  if (typeof userId !== 'string' || userId.trim() === '') {
    return { valid: false, reason: 'userId must be a non-empty string', normalizedContext: null };
  }

  const validRoles = Object.values(ROLES);
  if (!role || !validRoles.includes(role)) {
    return { valid: false, reason: `Unknown or invalid role: ${role}`, normalizedContext: null };
  }

  if (!authorization || typeof authorization !== 'object') {
    return { valid: false, reason: 'authorization object is required', normalizedContext: null };
  }

  const { scopeLevel, registeredFarmDistrict, authorizedDistricts, assignedFarmIds } = authorization;

  const validScopeLevels = Object.values(SCOPE_LEVELS);
  if (!scopeLevel || !validScopeLevels.includes(scopeLevel)) {
    return { valid: false, reason: `Unknown or invalid scopeLevel: ${scopeLevel}`, normalizedContext: null };
  }

  // Enforce role-to-scope compatibility
  const allowedScopes = ROLE_ALLOWED_SCOPES[role] || [];
  if (!allowedScopes.includes(scopeLevel)) {
    return {
      valid: false,
      reason: `Incompatible scopeLevel '${scopeLevel}' for role '${role}'`,
      normalizedContext: null,
    };
  }

  if (!Array.isArray(authorizedDistricts)) {
    return { valid: false, reason: 'authorizedDistricts must be an array', normalizedContext: null };
  }

  if (!Array.isArray(assignedFarmIds)) {
    return { valid: false, reason: 'assignedFarmIds must be an array', normalizedContext: null };
  }

  if (!permissions || typeof permissions !== 'object' || Array.isArray(permissions)) {
    return { valid: false, reason: 'permissions must be an object', normalizedContext: null };
  }

  let cleanRegisteredFarmDistrict = null;
  let cleanAuthorizedDistricts = [];
  let cleanAssignedFarmIds = [];

  if (role === ROLES.FARMER) {
    if (typeof registeredFarmDistrict !== 'string' || registeredFarmDistrict.trim() === '') {
      return { valid: false, reason: 'FARMER role requires a valid non-empty registeredFarmDistrict', normalizedContext: null };
    }
    cleanRegisteredFarmDistrict = registeredFarmDistrict.trim();
    // Farmer authorizedDistricts strictly restricted to registered farm district
    cleanAuthorizedDistricts = [cleanRegisteredFarmDistrict];
    cleanAssignedFarmIds = [];
  } else if (role === ROLES.VETERINARY_OFFICER) {
    cleanRegisteredFarmDistrict = null;
    cleanAuthorizedDistricts = Array.from(
      new Set(
        authorizedDistricts
          .filter((d) => typeof d === 'string' && d.trim() !== '')
          .map((d) => d.trim())
      )
    );
    cleanAssignedFarmIds = Array.from(
      new Set(
        assignedFarmIds
          .filter((f) => typeof f === 'string' && f.trim() !== '')
          .map((f) => f.trim())
      )
    );
  } else if (role === ROLES.DAPH_OFFICIAL) {
    cleanRegisteredFarmDistrict = null;
    cleanAuthorizedDistricts = Array.from(
      new Set(
        authorizedDistricts
          .filter((d) => typeof d === 'string' && d.trim() !== '')
          .map((d) => d.trim())
      )
    );
    cleanAssignedFarmIds = [];
  }

  // Strict boolean normalization for permissions
  const normalizedPermissions = {
    viewDataQuality: permissions.viewDataQuality === true,
    viewModelTransparency: permissions.viewModelTransparency === true,
    manageAlerts: permissions.manageAlerts === true,
    recordResponse: permissions.recordResponse === true,
    viewReports: permissions.viewReports === true,
  };

  const normalizedContext = {
    userId: userId.trim(),
    role,
    authorization: {
      scopeLevel,
      registeredFarmDistrict: cleanRegisteredFarmDistrict,
      authorizedDistricts: cleanAuthorizedDistricts,
      assignedFarmIds: cleanAssignedFarmIds,
    },
    permissions: normalizedPermissions,
  };

  return {
    valid: true,
    reason: null,
    normalizedContext,
  };
}

/**
 * Access Selector: Registered Farm District
 * Returns district only for a valid FARMER context with FARM scopeLevel.
 *
 * @param {Object} viewerContext
 * @returns {string | null}
 */
export function getRegisteredFarmDistrict(viewerContext) {
  const { valid, normalizedContext } = validateViewerContext(viewerContext);
  if (!valid || normalizedContext.role !== ROLES.FARMER) {
    return null;
  }
  return normalizedContext.authorization.registeredFarmDistrict || null;
}

/**
 * Access Selector: Authorized Districts
 * Returns a new array of authorized districts from valid context.
 *
 * @param {Object} viewerContext
 * @returns {string[]}
 */
export function getAuthorizedDistricts(viewerContext) {
  const { valid, normalizedContext } = validateViewerContext(viewerContext);
  if (!valid) {
    return [];
  }
  return [...normalizedContext.authorization.authorizedDistricts];
}

/**
 * Access Selector: Assigned Farm IDs
 * Returns assigned farm IDs only for a valid VETERINARY_OFFICER context.
 *
 * @param {Object} viewerContext
 * @returns {string[]}
 */
export function getAssignedFarmIds(viewerContext) {
  const { valid, normalizedContext } = validateViewerContext(viewerContext);
  if (!valid || normalizedContext.role !== ROLES.VETERINARY_OFFICER) {
    return [];
  }
  return [...normalizedContext.authorization.assignedFarmIds];
}

/**
 * Access Selector: Has Forecasting Permission
 * Evaluates strict boolean capability permission for viewer.
 *
 * @param {Object} viewerContext
 * @param {string} permission
 * @returns {boolean}
 */
export function hasForecastingPermission(viewerContext, permission) {
  if (!permission || !Object.prototype.hasOwnProperty.call(PERMISSIONS, permission)) {
    return false;
  }
  const { valid, normalizedContext } = validateViewerContext(viewerContext);
  if (!valid) {
    return false;
  }
  return normalizedContext.permissions[permission] === true;
}

/**
 * Access Selector: Can Access Forecasting Role
 * Verifies if viewer context matches the specified canonical role.
 *
 * @param {Object} viewerContext
 * @param {string} role
 * @returns {boolean}
 */
export function canAccessForecastingRole(viewerContext, role) {
  if (!role || !Object.values(ROLES).includes(role)) {
    return false;
  }
  const { valid, normalizedContext } = validateViewerContext(viewerContext);
  if (!valid) {
    return false;
  }
  return normalizedContext.role === role;
}
