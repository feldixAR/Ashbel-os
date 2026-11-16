"""Native deterministic experts with inspectable task contracts, not LLM agents.

Each execute() computes a role-specific result. The auditor is a distinct expert
and checks the CEO decision against the role outputs and evidence.
"""
from agents.base.base_agent import BaseAgent
from services.execution.executor import ExecutionResult

ROLES = ('sales', 'engineering', 'procurement', 'finance', 'marketing',
         'strategy', 'pmo', 'knowledge', 'auditor')

CONTRACTS = {
    'sales': 'Verify contact permission and prepare the next message decision without sending.',
    'engineering': 'Check approved specification before pricing or production; never invent manufacturer formulas.',
    'procurement': 'Check supplier capacity and comparability of procurement scope, not historical selling prices.',
    'finance': 'Separate proposals, procurement, ancillary costs and collections; unknown amounts remain null.',
    'marketing': 'Check source provenance, deduplication and contact permission before lead expansion.',
    'strategy': 'Check direct-contractor feasibility including manufacturing, installation, liability and cash flow.',
    'pmo': 'Preserve open loops, owners, dates and completion evidence.',
    'knowledge': 'Preserve event identity, source reference and source-context version.',
    'auditor': 'Independently reject unsupported CEO claims or permission/capacity/collection violations.',
}


def role_contract(role):
    return {'role': role, 'task': CONTRACTS[role], 'mode': 'native_deterministic',
            'sources': ['event source_ref and immutable facts', 'existing business-source adapter context'],
            'permissions': {'external_send': False, 'spend': False, 'source_write': False},
            'expected_output': 'action/no_change/missing_data with evidence and explicit gaps',
            'success_criteria': ['source provenance retained', 'unknown facts not promoted',
                                 'no external side effect', 'actual execution trace persisted']}


def roles_for(event_type):
    roles = {'pmo', 'knowledge', 'finance', 'strategy'}
    if event_type in {'customer.updated', 'opportunity.discovered', 'message.received', 'message.status'}:
        roles.add('sales')
    if event_type in {'quote.received', 'supplier.updated'}:
        roles.update(('engineering', 'procurement'))
    if event_type == 'opportunity.discovered':
        roles.add('marketing')
    if event_type == 'source.snapshot':
        roles.update(ROLES[:-1])
    return [role for role in ROLES[:-1] if role in roles]


class DepartmentExpert(BaseAgent):
    version = 1

    def __init__(self, role):
        if role not in ROLES:
            raise ValueError('unknown_department')
        self.role = self.department = role
        self.agent_id = 'native_business_' + role + '_v1'
        self.name = 'Native business ' + role

    def can_handle(self, task_type, action):
        return task_type == 'business_event_department' and action == self.role

    def execute(self, task):
        try:
            data = task.input_data
            event, context = data['event'], data['context']
            result = self.analyze(event, context, data.get('previous', {}))
            return ExecutionResult(success=True, message=result['summary'], output=result)
        except Exception as exc:
            return ExecutionResult(success=False, message='department_execution_failed',
                                   output={'error_code': type(exc).__name__, 'mode': 'native_deterministic'})

    def analyze(self, event, context, previous):
        facts = event.get('facts', {})
        evidence = {'event_id': event['id'], 'source_ref': event['source_ref'],
                    'source_fingerprint': event['fingerprint'],
                    'context_fingerprint': context.get('snapshot_sha256'),
                    'source_ranges': context.get('source_ranges', [])}
        result = {'department': self.role, 'mode': 'native_deterministic',
                  'status': 'no_change', 'summary': 'אין שינוי מהותי בתחום זה.',
                  'actions': [], 'missing': [], 'evidence': evidence,
                  'permissions': {'external_send': False, 'spend': False, 'source_write': False}}
        def action(summary, code, **extra):
            result.update(status='action', summary=summary)
            result['actions'].append({'code': code, 'requires_owner_approval': False, **extra})
        def missing(summary, *fields):
            result.update(status='missing_data', summary=summary, missing=list(fields))
        if self.role == 'sales':
            if event['event_type'] == 'message.status':
                action('לתעד תשובת ספק שירות כהתקבל מידע, ללא המצאת מסירה.', 'reconcile_provider_status', execution='proposal_only')
            elif event['event_type'] == 'message.received':
                action('לסווג תשובה נכנסת ולהכין תגובה לאישור, ללא שליחה אוטומטית.', 'review_inbound', execution='proposal_only')
            elif facts.get('contact_permission') != 'specific_consent_verified':
                missing('אין הרשאה ספציפית מאומתת לפנייה; אפשר להכין טיוטה בלבד.', 'contact_permission')
            else:
                action('להכין פנייה אישית לאישור ספציפי לנמען ולנוסח.', 'draft_for_specific_approval', execution='proposal_only')
        elif self.role == 'engineering':
            if facts.get('specification_approved') is not True:
                missing('נדרש מפרט מאושר לפני תמחור מתקדם או ייצור.', 'approved_specification')
            else:
                action('להשוות מפרט מאושר לשורות הצעת מקור; אין נוסחת ייצור אוטומטית.', 'source_quote_review', execution='proposal_only')
        elif self.role == 'procurement':
            if context.get('capacity_state') != 'confirmed':
                action('להכשיר ספק ייצור וקיבולת; קשר חיצוני והעברת חומר דורשים אישור.', 'qualify_supplier', execution='internal_preparation_only')
            else:
                action('להשוות הצעות רכש על מפרט זהה, תכולה ותנאי אחריות.', 'compare_verified_purchase_quotes', execution='proposal_only')
        elif self.role == 'finance':
            # Sales prices, proposed commissions and ready-for-proposal flags never
            # become contractor procurement costs or collections.
            missing('אין להכיר גבייה או רווח מאומת מתוך הצעה; נדרשות עלויות רכש ואסמכתאות.',
                    'verified_purchase_costs', 'ancillary_costs', 'payment_terms', 'collection_evidence')
            result['financial_truth'] = {'collected_ils': None, 'verified_contractor_profit_ils': None}
        elif self.role == 'marketing':
            if context.get('capacity_state') != 'confirmed':
                missing('אפשר לחקור הזדמנויות; אין להרחיב פניות לפני אימות קיבולת והרשאה.', 'supplier_capacity', 'contact_permission')
            else:
                action('לבדוק הזדמנות מול המאגר הקיים לפי מקור ומזהים לפני קליטה.', 'deduplicate_external_opportunity', execution='proposal_only')
        elif self.role == 'strategy':
            action('לקדם מודל קבלן ראשי רק על בסיס רכש, התקנה, אחריות ותזרים מאומתים.', 'contractor_feasibility_gate', execution='internal_preparation_only')
            result['business_model'] = 'direct_contractor_with_separate_manufacturing_and_installation'
        elif self.role == 'pmo':
            action('לשמר מעקבים וראיות עד תוצאה; אין לסגור משימות עקב יצירת דוח.', 'maintain_open_loops', execution='internal_preparation_only')
            result['open_loop_count'] = len([a for a in context.get('actions', []) if a.get('disposition') != 'completed'])
        elif self.role == 'knowledge':
            action('נשמרו מקור, גרסה וטביעת תוכן לאירוע ולתוצאות המחלקות.', 'preserve_provenance', execution='persisted_event_audit')
        elif self.role == 'auditor':
            violations = []
            decision = previous.get('ceo_decision', {})
            departments = previous.get('departments', {})
            if not evidence['source_ref'] or not evidence['context_fingerprint']:
                violations.append('missing_provenance')
            if any(d.get('mode') != 'native_deterministic' for d in departments.values()):
                violations.append('unproven_agent_mode')
            if context.get('capacity_state') != 'confirmed' and decision.get('code') == 'expand_outreach':
                violations.append('capacity_gate_bypassed')
            if decision.get('executed_external_action') is not False:
                violations.append('external_execution_not_proven')
            if decision.get('collected_ils') is not None:
                violations.append('unproven_collection')
            if not departments or any(not d.get('evidence') for d in departments.values()):
                violations.append('missing_department_evidence')
            result.update(status='action' if violations else 'no_change',
                          summary='נמצאו הפרות המחייבות חסימה.' if violations else 'ההכרעה עומדת בשערי מקור, הרשאה וכסף.',
                          passed=not violations, violations=violations)
        return result


def register_department_experts():
    from agents.base.agent_registry import agent_registry
    for role in ROLES:
        agent_registry.register(DepartmentExpert(role))
