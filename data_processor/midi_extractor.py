# midi quantizer
# Extract the quantized midi into main melody, bass, and texture 
from collections import defaultdict
import mido
import numpy as np
import pretty_midi as pyd


class MidiExtractor:

    '''
    bpm: the bpm to fix
    note_thres: the max and min note
    denominator: time_signature threshold
    '''
    def __init__(self, bpm = 120, note_thres = [24, 108], denominator_thres = [2, 4, 8]):
        self.bpm = bpm
        self.beat_time = 60.0 / bpm # 0.5s for 120 bpm
        self.note_thres = note_thres
        self.denominator_thres = denominator_thres
    
    '''
    process a quantized midi file to main melody, bass and texture
    midi_file: midi_file address
    return: 
        a dict with bass, melody, and texture, and time_signature
        each track is based on measure unit, which contains a series of notes in onset-pitch order
        each note is represented by [pitch, start_tick, end_tick, velocity]
        each tick is 1/12 beat in the according time_signature (i.e. 12 for 1/4 note, or 12 for 1/8 note)
    
    '''
    def process(self, midi_file, dataset_name = "default"):
        filename = midi_file
        midi_file = pyd.PrettyMIDI(midi_file, initial_tempo=self.bpm)
        # get max/min notes
        for ins in midi_file.instruments:
            notes = [d.pitch for d in ins.notes]
            if min(notes) < self.note_thres[0] or max(notes) > self.note_thres[1]:
                print(filename, "has a too much high/low note, ignored")
                return None
        # get time signature changes 
        ts = midi_file.time_signature_changes
        for temp_ts in ts:
            if temp_ts.denominator not in self.denominator_thres:
                print(filename, "has an invalid denomiator, ignored")
                return None
        # start to process
        if "POP909" in dataset_name: # POP909 has already had a melody/bridge data
            pass
        else:
            # combine all tracks together:
            all_notes = []
            for ins in midi_file.instruments:
                notes = [[d.pitch, d.start, d.end, d.velocity] for d in ins.notes]
                all_notes += notes
            all_notes.sort(key = lambda x: (x[1], x[0]))
            ts_note_group = []
            # extract note along with ts
            cur_pos = 0 # note header
            cur_bt = 60.0 / self.bpm / 12 # current beat time default: 60 / bpm / 12
            for i, cur_ts in enumerate(ts):
                temp = [] # temp_tsnote_group
                cur_bt = 60 / self.bpm / 12 * 4 / cur_ts.denominator # get the cur beat time
                ts_time = round(cur_ts.time / cur_bt)
                if i == len(ts) - 1:
                    for note in all_notes[cur_pos:]:
                        p, sta, end, vel = note
                        sta = max(round(sta / cur_bt), ts_time)
                        end = round(end / cur_bt)
                        if sta > ts_time and (sta - 1) % 12 == 0:
                            sta -= 1
                            end -= 1
                        elif (sta + 1) % 12 == 0:
                            sta += 1
                            end += 1
                        
                        temp.append([p, sta, end, vel])
                        cur_pos += 1
                    temp.sort(key = lambda x: (x[1], x[0]))
                    ts_note_group.append(temp)
                else:
                    end_ts_time = round(ts[i+1].time / cur_bt)
                    while cur_pos < len(all_notes):
                        p, sta, end, vel = all_notes[cur_pos]
                        sta = max(round(sta / cur_bt), ts_time)
                        end = min(round(end / cur_bt), end_ts_time)
                        if sta > ts_time and (sta - 1) % 12 == 0:
                            sta -= 1
                            end -= 1
                        elif (sta + 1) % 12 == 0:
                            sta += 1
                            end += 1
                        if ts_time <= sta < end_ts_time:
                            temp.append([p, sta, end, vel])
                        else:
                            break
                        cur_pos += 1
                    temp.sort(key =lambda x: (x[1], x[0]))
                    ts_note_group.append(temp)
            assert len(ts) == len(ts_note_group), "the length of time signature must be equal to the note groups"
            # extract main melody, bass, and texture 
            bass_note_group = []
            melody_note_group = []
            texture_note_group = []
            last_bass = 24
            last_melody = 108
            for i, cur_ts in enumerate(ts):
                onset_dict = {}
                cur_note_group = ts_note_group[i]
                bassline = []
                melody_line = []
                texture_line = []
                for j, note in enumerate(cur_note_group):
                    sta = note[1]
                    if j == len(cur_note_group) - 1:
                        if sta not in onset_dict:
                            onset_dict[sta] = True
                            if (last_melody + last_bass) // 2 < note[0]:
                                melody_line.append(note[::])
                                last_melody = note[0]
                            else:
                                bassline.append(note[::])
                                last_bass = note[0]
                        else:
                            melody_line.append(note[::])
                            last_melody = note[0]
                    else:
                        if sta not in onset_dict:
                            onset_dict[sta] = True
                            if sta != cur_note_group[j + 1][1]:
                                if len(bassline) == 0 or len(melody_line) == 0:
                                    melody_line.append(note[::])
                                    last_melody = note[0]
                                else:
                                    if (last_melody + last_bass) // 2 < note[0]:
                                        melody_line.append(note[::])
                                        last_melody = note[0]
                                    else:
                                        bassline.append(note[::])
                                        last_bass = note[0]
                            else:
                                bassline.append(note[::])
                                last_bass = note[0]
                        else:
                            if sta != cur_note_group[j + 1][1]:
                                melody_line.append(note[::])
                                last_melody = note[0]
                            else:
                                texture_line.append(note[::])
                bass_note_group.append(bassline)
                melody_note_group.append(melody_line)
                texture_note_group.append(texture_line)
            assert len(ts) == len(bass_note_group) == len(melody_note_group) == len(texture_note_group), "the length of time signature must be equal to the note groups"

            # # detect the double-bass-melody

            # # find the anchor
            # melody_anchor = -1
            # bass_anchor = -1
            # m_pos = 0 # melody pos
            # b_pos = 0 # bass pos
            # ts_pos = 0 # time signature pos
            # while ts_pos < len(ts):
            #     m_pos = 0
            #     b_pos = 0
            #     while m_pos < len(melody_note_group[ts_pos]) and b_pos 
 
            # todo: convert to different measure
            return {
                "bass": bass_note_group,
                "melody": melody_note_group,
                "texture": texture_note_group,
                "ts": [[d.numerator, d.denominator, d.time] for d in ts]
            }
    '''
    reconstruct a midi file from a midi dict
    midi_file: output midi_file address
    '''
    def reconstruct(self, midi_dict, midi_file):
        bass_note_group = midi_dict["bass"]
        melody_note_group = midi_dict["melody"]
        texture_note_group = midi_dict["texture"]
        ts = midi_dict["ts"]
        m_midi = pyd.PrettyMIDI(initial_tempo=120)
        for temp_ts in ts:
            num, denom, time = temp_ts
            m_midi.time_signature_changes.append(pyd.TimeSignature(num, denom, time))

        # define tracks
        melody_ins = pyd.Instrument(program=0, name = "Melody")
        bass_ins = pyd.Instrument(program=0, name = "Bass")
        texture_ins = pyd.Instrument(program=0, name = "Texture")

        # write main melody
        for i, group in enumerate(melody_note_group):
            num, denom, time = ts[i]
            cur_bt = 60/ self.bpm / 12 * 4 / denom
            for note in group:
                p, sta, end, vel = note
                sta = sta * cur_bt
                end = end * cur_bt
                melody_ins.notes.append(pyd.Note(vel, p, sta, end))
        m_midi.instruments.append(melody_ins)

        # write texture
        for i, group in enumerate(texture_note_group):
            num, denom, time = ts[i]
            cur_bt = 60/ self.bpm / 12 * 4 / denom
            for note in group:
                p, sta, end, vel = note
                sta = sta * cur_bt
                end = end * cur_bt
                texture_ins.notes.append(pyd.Note(vel, p, sta, end))
        m_midi.instruments.append(texture_ins)

        # write bass
        for i, group in enumerate(bass_note_group):
            num, denom, time = ts[i]
            cur_bt = 60/ self.bpm / 12 * 4 / denom
            for note in group:
                p, sta, end, vel = note
                sta = sta * cur_bt
                end = end * cur_bt
                bass_ins.notes.append(pyd.Note(vel, p, sta, end))
        m_midi.instruments.append(bass_ins)

        m_midi.write(midi_file)
        
