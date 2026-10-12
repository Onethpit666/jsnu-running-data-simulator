"""Encode native FIT fields with Garmin's official SDK, using a development identity."""
import math
from garmin_fit_sdk import Encoder, Profile, FIT_EPOCH_S
from garmin_fit_sdk.fit import BASE_TYPE


def timestamp(time):
    return int(time.timestamp())-FIT_EPOCH_S


def serialize(activity):
    summary=activity.summary()
    start,end=timestamp(activity.start),timestamp(activity.points[-1].time)
    developer_id={'mesg_num':Profile['mesg_num']['DEVELOPER_DATA_ID'],
                  'application_id':list(bytes.fromhex('3f3c050be4a945b497a22cded1e05190')),
                  'application_version':3,'developer_data_index':0}
    descriptions={}
    fields=[('synthetic_source','uint8','flag'),('synthetic_srpe_load','float32','AU')]
    for key,(name,kind,unit) in enumerate(fields):
        desc={'mesg_num':Profile['mesg_num']['FIELD_DESCRIPTION'],'developer_data_index':0,
              'field_definition_number':key,'fit_base_type_id':BASE_TYPE[kind.upper()],
              'field_name':name,'units':unit,'native_mesg_num':Profile['mesg_num']['SESSION']}
        descriptions[key]={'developer_data_id_mesg':developer_id,'field_description_mesg':desc}
    encoder=Encoder(field_descriptions=descriptions)
    def write(name,**fields):
        encoder.write_mesg(dict(mesg_num=Profile['mesg_num'][name.upper()],**fields))
    write('file_id',type='activity',manufacturer='development',product=0,time_created=start)
    write('device_info',device_index='creator',manufacturer='development',product=0,
          product_name='Synthetic Run File Studio',software_version=3,timestamp=start)
    encoder.write_mesg(developer_id)
    for desc in descriptions.values():
        encoder.write_mesg(desc['field_description_mesg'])
    write('event',timestamp=start,event='timer',event_type='start')
    for i,p in enumerate(activity.points):
        if p.paused:
            write('event',timestamp=timestamp(activity.points[i-1].time),event='timer',event_type='stop_all')
        record=dict(timestamp=timestamp(p.time),time128=p.time.microsecond/1e6,
                    position_lat=round(p.lat*2**31/180),position_long=round(p.lon*2**31/180),
                    distance=p.distance_m,enhanced_speed=p.speed_mps)
        if p.hr is not None:
            record['heart_rate']=p.hr
        if p.altitude_m is not None:
            record.update(enhanced_altitude=p.altitude_m,power=round(p.power_w),
                          cadence=math.floor(p.cadence_spm/2),
                          fractional_cadence=p.cadence_spm/2%1,step_length=p.stride_m*1000)
        write('record',**record)
        if p.paused:
            write('event',timestamp=timestamp(p.time),event='timer',event_type='start')
    write('event',timestamp=end,event='timer',event_type='stop_all')
    stats=dict(timestamp=end,start_time=start,total_elapsed_time=activity.elapsed_duration_s,
               total_timer_time=activity.duration_s,total_distance=activity.distance_m,
               sport='running',sub_sport='generic',
               enhanced_avg_speed=activity.distance_m/activity.duration_s,
               enhanced_max_speed=activity.max_speed)
    if summary['average_hr'] is not None:
        stats.update(avg_heart_rate=summary['average_hr'],max_heart_rate=summary['max_hr'])
    if activity.params.simulate_metrics:
        cadence=summary['average_cadence_spm']/2
        stats.update(total_calories=summary['calories_kcal'],total_ascent=round(summary['ascent_m']),
                     avg_cadence=math.floor(cadence),avg_fractional_cadence=cadence%1,
                     max_cadence=round(max(p.cadence_spm for p in activity.points)/2),
                     avg_power=round(summary['average_power_w']),max_power=round(max(p.power_w for p in activity.points)),
                     avg_step_length=summary['average_stride_m']*1000)
    write('lap',message_index=0,**stats)
    write('session',message_index=0,first_lap_index=0,num_laps=1,**stats,
          developer_fields={0:1,1:summary.get('training_load_estimate',0)})
    write('activity',timestamp=end,total_timer_time=activity.duration_s,num_sessions=1,
          type='manual',event='activity',event_type='stop',local_timestamp=end+8*3600)
    return bytes(encoder.close())
