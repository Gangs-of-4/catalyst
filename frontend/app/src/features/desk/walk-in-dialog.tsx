import { Loader2 } from "lucide-react";
import * as React from "react";

import { Field } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ApiError } from "@/lib/api";

import { addBooking, type Alternative, type Doctor, time12 } from "./api";

export type WalkInTarget = { doctor: Doctor; date: string; time: string; dayLabel: string };

type Props = {
  target: WalkInTarget | null;
  doctors: Doctor[];
  onClose: () => void;
  onSaved: (target: WalkInTarget, name: string) => void;
};

/**
 * Add a booking for someone at the counter or on WhatsApp. What was typed is kept through any error;
 * a taken or closed time offers the free times nearby as one-tap choices (contracts.md §6.1).
 * The page gives it a `key` per tapped slot, so each slot starts a fresh form.
 */
export function WalkInDialog({ target, doctors, onClose, onSaved }: Props) {
  const [slot, setSlot] = React.useState<WalkInTarget | null>(target);
  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [source, setSource] = React.useState<"walk_in" | "whatsapp">("walk_in");
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);
  const [alternatives, setAlternatives] = React.useState<Alternative[]>([]);
  const [saving, setSaving] = React.useState(false);

  const doctorName = (id: string) => doctors.find((d) => d.id === id)?.name ?? id;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!slot || saving) return;
    if (!name.trim()) {
      setErrors({ name: "Please write the patient's name." });
      return;
    }
    setSaving(true);
    setErrors({});
    setProblem(null);
    setAlternatives([]);
    try {
      await addBooking({
        doctor_id: slot.doctor.id,
        date: slot.date,
        time: slot.time,
        name: name.trim(),
        phone: phone.trim() || null,
        source,
      });
      onSaved(slot, name.trim());
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fields);
        setProblem(Object.keys(err.fields).length ? null : err.detail);
        setAlternatives((err.alternatives as Alternative[]).filter((a) => a && typeof a.time === "string"));
      } else {
        setProblem("Couldn't save the booking. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  function pick(a: Alternative) {
    if (!slot) return;
    const doctor = doctors.find((d) => d.id === a.doctor_id) ?? slot.doctor;
    setSlot({ ...slot, doctor, date: a.date, time: a.time, dayLabel: a.date === slot.date ? slot.dayLabel : a.date });
    setProblem(null);
    setAlternatives([]);
  }

  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && !saving && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a booking</DialogTitle>
          {slot && (
            <DialogDescription>
              {slot.doctor.name} · {time12(slot.time)} · {slot.dayLabel}
            </DialogDescription>
          )}
        </DialogHeader>

        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <Field label="Patient's name" error={errors.name}>
            <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" maxLength={80} autoFocus />
          </Field>
          <Field label="Mobile number" optional error={errors.phone} hint="For the reminder. 10 digits.">
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} type="tel" inputMode="tel" autoComplete="off" />
          </Field>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 text-sm font-medium">Came in by</legend>
            <RadioGroup value={source} onValueChange={(v) => setSource(v as "walk_in" | "whatsapp")} className="flex gap-6">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="walk_in" id="src-walk-in" />
                <Label htmlFor="src-walk-in">Walk-in</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="whatsapp" id="src-whatsapp" />
                <Label htmlFor="src-whatsapp">WhatsApp</Label>
              </div>
            </RadioGroup>
          </fieldset>

          {problem && (
            <div role="alert" className="flex flex-col gap-2 rounded-md bg-destructive-soft px-3 py-2.5 text-sm text-destructive-text">
              <p>{problem}</p>
              {alternatives.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {alternatives.map((a) => (
                    <Button key={`${a.doctor_id}-${a.date}-${a.time}`} size="sm" variant="outline" onClick={() => pick(a)}>
                      {time12(a.time)} · {doctorName(a.doctor_id)}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={onClose} disabled={saving}>
              Back
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 aria-hidden className="animate-spin" />} Save booking
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
