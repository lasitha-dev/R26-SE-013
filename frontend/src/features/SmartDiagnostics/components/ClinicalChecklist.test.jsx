import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ClinicalChecklist from './ClinicalChecklist';

describe('ClinicalChecklist', () => {
  it('shows reported welfare concerns before the checklist is complete', () => {
    render(<ClinicalChecklist diseaseKey="mastitis" onAssess={vi.fn()} onEdit={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/Systemic illness assessed/), { target: { value: 'true' } });
    expect(screen.getByRole('alert')).toHaveTextContent('prompt veterinary assessment');
    expect(screen.getByRole('button')).toBeDisabled();
  });
  it('keeps unknown mastitis observations distinct from examined negatives', () => {
    const assess = vi.fn();
    const edit = vi.fn();
    render(<ClinicalChecklist diseaseKey="mastitis" onAssess={assess} onEdit={edit} />);
    const button = screen.getByRole('button', { name: 'Assess clinical observations' });
    expect(button).toBeDisabled();
    screen.getAllByRole('combobox').forEach((element, index) => {
      fireEvent.change(element, { target: { value: index === 0 ? 'true' : 'false' } });
    });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(button);
    expect(assess).toHaveBeenCalledWith({ disease: 'mastitis', vet_confirmed: true,
      milk_abnormal: true, udder_inflammation: false, systemic_illness: false });
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '' } });
    expect(button).toBeDisabled();
    expect(edit).toHaveBeenCalledTimes(5);
  });

  it('sends measured centimetres and a count of affected feet for FMD', () => {
    const assess = vi.fn();
    render(<ClinicalChecklist diseaseKey="foot_and_mouth" onAssess={assess} onEdit={vi.fn()} />);
    const entries = [
      [/Affected feet/, '3'], [/Appetite/, 'reduced'], [/Behaviour/, 'slightly_dull'],
      [/Heel and coronary/, 'false'], [/Unable to stand/, 'false'],
    ];
    entries.forEach(([label, value]) => fireEvent.change(screen.getByLabelText(label), { target: { value } }));
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '5.0' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button'));
    expect(assess).toHaveBeenCalledWith({ disease: 'foot_and_mouth', vet_confirmed: true,
      affected_feet: 3, mouth_lesion_cm: 5, appetite: 'reduced', mentation: 'slightly_dull',
      heel_and_coronary_involved: false, unable_to_stand: false });
  });
});
