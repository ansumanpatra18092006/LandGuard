-- OPTIONAL SIH DEMO DATA ONLY.
-- Adds fictional schedule/cost inputs to the eight illustrative Rayagada projects
-- so the real PAIMANA baseline can run end-to-end. These values are NOT claims
-- about real government projects.

update public.projects set original_cost_crore=420, expenditure_crore=155, original_end_date='2027-03-31', updated_at=now() where project_id='P-RGD-001';
update public.projects set original_cost_crore=310, expenditure_crore=226, original_end_date='2026-12-31', updated_at=now() where project_id='P-RGD-002';
update public.projects set original_cost_crore=880, expenditure_crore=188, original_end_date='2027-06-30', updated_at=now() where project_id='P-RGD-003';
update public.projects set original_cost_crore=260, expenditure_crore=231, original_end_date='2026-11-30', updated_at=now() where project_id='P-RGD-004';
update public.projects set original_cost_crore=540, expenditure_crore=245, original_end_date='2027-02-28', updated_at=now() where project_id='P-RGD-005';
update public.projects set original_cost_crore=195, expenditure_crore=187, original_end_date='2026-10-31', updated_at=now() where project_id='P-RGD-006';
update public.projects set original_cost_crore=720, expenditure_crore=398, original_end_date='2027-01-31', updated_at=now() where project_id='P-RGD-007';
update public.projects set original_cost_crore=175, expenditure_crore=139, original_end_date='2026-12-15', updated_at=now() where project_id='P-RGD-008';
